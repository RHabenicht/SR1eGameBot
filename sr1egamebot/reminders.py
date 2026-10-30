"""Reminder record compatibility and post-login scheduling."""

from __future__ import annotations

import asyncio
import secrets
import re
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from .repository import LegacyRepository


_REMINDER_FIELDS = (
    "shortID", "id", "sessionTimeDateF", "dateTime", "timeStamp",
    "gmID", "userFolderID", "playChannelID", "playersString",
)


def parse_datetime(value: str) -> datetime:
    """Parse ISO timestamps and the legacy JavaScript Date.toString format."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError:
        legacy = normalized.split(" (")[0]
        result = datetime.strptime(legacy, "%a %b %d %Y %H:%M:%S GMT%z")
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def serialize_reminder(reminder: dict[str, Any]) -> str:
    """Write the same nine comma-separated fields as the Node application."""
    values = [str(reminder.get(field, "")) for field in _REMINDER_FIELDS]
    return ",".join(values)


def parse_reminder_records(content: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for line in content.split("\n"):
        if not line:
            continue
        fields = line.split(",")
        if len(fields) < len(_REMINDER_FIELDS):
            continue
        record = dict(zip(_REMINDER_FIELDS, fields[:len(_REMINDER_FIELDS)]))
        # Old user reminder files call the public short identifier smallID.
        record["smallID"] = record["shortID"]
        records.append(record)
    return records


class ReminderManager:
    """Own in-process reminder timers, restored only after Discord is ready."""

    def __init__(self, deliver: Callable[[dict[str, Any]], Awaitable[None]],
                 on_error: Callable[[BaseException], Any] = lambda _error: None,
                 on_delivered: Callable[[dict[str, Any]], Awaitable[None]] | None = None) -> None:
        self.reminders: list[dict[str, Any]] = []
        self._deliver = deliver
        self._on_error = on_error
        self._on_delivered = on_delivered
        self._timers: dict[str, asyncio.TimerHandle] = {}
        self._started = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def restore(self, content: str) -> list[dict[str, Any]]:
        self.reminders = parse_reminder_records(content)
        return self.reminders

    def set_on_delivered(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self._on_delivered = callback

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._loop = asyncio.get_running_loop()
        now = datetime.now(timezone.utc).timestamp() * 1000
        for reminder in self.reminders:
            try:
                timestamp = float(reminder["timeStamp"])
            except (KeyError, ValueError):
                timestamp = parse_datetime(reminder["dateTime"]).timestamp() * 1000
            self._schedule(reminder, max(0, timestamp - now) / 1000)

    def add(self, reminders: Sequence[dict[str, Any]]) -> None:
        self.reminders.extend(reminders)
        if self._started:
            for reminder in reminders:
                delay = max(0, float(reminder.get(
                    "MilliSecondsFromNow",
                    float(reminder["timeStamp"]) - datetime.now(timezone.utc).timestamp() * 1000,
                )) / 1000)
                self._schedule(reminder, delay)

    def cancel(self, short_ids: set[str]) -> int:
        before = len(self.reminders)
        retained = []
        for reminder in self.reminders:
            key = str(reminder.get("id", ""))
            if reminder.get("shortID") in short_ids or reminder.get("smallID") in short_ids:
                timer = self._timers.pop(key, None)
                if timer is not None:
                    timer.cancel()
            else:
                retained.append(reminder)
        self.reminders = retained
        return before - len(retained)

    def remove(self, reminder_id: str) -> None:
        self.reminders = [r for r in self.reminders if str(r.get("id")) != reminder_id]
        timer = self._timers.pop(reminder_id, None)
        if timer is not None:
            timer.cancel()

    def stop(self) -> None:
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
        self._started = False

    def _schedule(self, reminder: dict[str, Any], delay: float) -> None:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        reminder_id = str(reminder.get("id", secrets.token_hex(32)))
        reminder["id"] = reminder_id
        old = self._timers.pop(reminder_id, None)
        if old is not None:
            old.cancel()
        self._timers[reminder_id] = self._loop.call_later(
            delay, self._begin_delivery, reminder_id, reminder
        )

    def _begin_delivery(self, reminder_id: str, reminder: dict[str, Any]) -> None:
        self._timers.pop(reminder_id, None)
        asyncio.create_task(self._run_delivery(reminder))

    async def _run_delivery(self, reminder: dict[str, Any]) -> None:
        try:
            await self._deliver(reminder)
            if self._on_delivered is not None:
                await self._on_delivered(reminder)
        except BaseException as error:
            self._on_error(error)


class ReminderService:
    """Store reminder payloads in the legacy per-GM and active-reminder files."""

    def __init__(self, repository: LegacyRepository, manager: ReminderManager,
                 reminder_root_id: Callable[[], str]) -> None:
        self._repository = repository
        self._manager = manager
        self._reminder_root_id = reminder_root_id

    async def restore(self) -> list[dict[str, Any]]:
        record = await self._repository.find_string("activeReminders", self._reminder_root_id())
        return self._manager.restore(await self._repository.get_string(str(record["_id"])) if record else "")

    async def persist(self) -> None:
        root_id = self._reminder_root_id()
        content = "\n".join(serialize_reminder(reminder) for reminder in self._manager.reminders)
        await self._repository.set_string("activeReminders", root_id, content)

    async def cancel_for_gm(self, gm_id: str, play_channel_id: str, short_ids: set[str],
                            user_folder_id: str) -> int:
        removed = self._manager.cancel(short_ids)
        await self.persist()
        owned = [r for r in self._manager.reminders
                 if str(r.get("gmID")) == str(gm_id)
                 and str(r.get("playChannelID")) == str(play_channel_id)]
        content = "\n".join(serialize_reminder(reminder) for reminder in owned)
        await self._repository.set_string("gmReminders", user_folder_id, content)
        return removed

    async def complete(self, reminder: dict[str, Any]) -> None:
        """Remove a delivered reminder from both legacy persistence files."""
        reminder_id = str(reminder.get("id", ""))
        self._manager.remove(reminder_id)
        await self.persist()
        folder_id = str(reminder.get("userFolderID", ""))
        owned = [r for r in self._manager.reminders
                 if str(r.get("gmID")) == str(reminder.get("gmID"))
                 and str(r.get("playChannelID")) == str(reminder.get("playChannelID"))]
        content = "\n".join(serialize_reminder(item) for item in owned)
        await self._repository.set_string("gmReminders", folder_id, content)


class ReminderCommandService:
    def __init__(self, repository: LegacyRepository, manager: ReminderManager,
                 persistence: ReminderService,
                 add_status: Callable[[Any, str], Any] = lambda _msg, text: text) -> None:
        self._repository = repository
        self._manager = manager
        self._persistence = persistence
        self._add_status = add_status

    async def add(self, msg: Any, args: Sequence[str]) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        if not args:
            await msg.reply("The session date & time you entered was invalid. Check it carefully and try again.")
            return
        session_text = args[0]
        try:
            session_time = parse_datetime(session_text)
        except (ValueError, TypeError):
            await msg.reply("The session date & time you entered was invalid. Check it carefully and try again.")
            return
        play_channel = await self._repository.get_play_channel(msg.guild.id, msg.channel.id, msg.author.id)
        folder_id = await self._repository.ensure_user_folder(msg.guild.id, play_channel, msg.author.id)
        players_record = await self._repository.find_string("gmPlayers", str(folder_id))
        players = await self._repository.get_string(str(players_record["_id"])) if players_record else ""
        if not players:
            await msg.reply(f"You have no players in channel <#{play_channel}> yet to send reminders to.")
            return

        now_ms = datetime.now(timezone.utc).timestamp() * 1000
        created: list[dict[str, Any]] = []
        for timing in args[1:]:
            match = re.fullmatch(r"(\d+(?:\.\d+)?)([mhd])", timing, re.IGNORECASE)
            if not match:
                # The Node command ignored an unrecognized unit, yielding a
                # reminder for session time. Retain that behavior for old inputs.
                amount, unit = 0.0, ""
            else:
                amount, unit = float(match.group(1)), match.group(2).lower()
            units = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}
            target_ms = session_time.timestamp() * 1000 - amount * units.get(unit, 0)
            run_ms = max(15_000, target_ms - now_ms)
            created.append({
                "shortID": secrets.token_hex(3),
                "id": secrets.token_hex(32),
                "sessionTimeDateF": session_text,
                "dateTime": datetime.fromtimestamp(target_ms / 1000, timezone.utc).isoformat(),
                "timeStamp": target_ms,
                "gmID": str(msg.author.id),
                "userFolderID": str(folder_id),
                "playChannelID": str(play_channel),
                "playersString": players.replace(",", " "),
                "MilliSecondsFromNow": run_ms,
            })

        if not created:
            await msg.reply("0 reminders added. **NOTE:** Reminders are now based on GMT+0.")
            return
        self._manager.add(created)
        await self._append_gm_records(str(folder_id), created)
        await self._persistence.persist()
        await msg.reply(f"{len(created)} reminders added. **NOTE:** Reminders are now based on GMT+0.")

    async def list(self, msg: Any) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        play_channel = await self._repository.get_play_channel(msg.guild.id, msg.channel.id, msg.author.id)
        folder_id = await self._repository.ensure_user_folder(msg.guild.id, play_channel, msg.author.id)
        record = await self._repository.find_string("gmReminders", str(folder_id))
        content = await self._repository.get_string(str(record["_id"])) if record else ""
        reminders = parse_reminder_records(content)
        if not reminders:
            await msg.reply(f"You have no reminders set in channel <#{play_channel}>.")
            return
        entries = []
        for reminder in reminders:
            session = self._format_date(parse_datetime(reminder["sessionTimeDateF"]))
            people = ", ".join(f'<@{player}>' for player in reminder["playersString"].split(" "))
            entries.append(
                f"**ID:** {reminder['shortID']}\n"
                f"**Reminder Time/Date:** {reminder['dateTime']}\n"
                f"**Session Time/Date:** {session}\n"
                f"**Players to Remind:** {people}"
            )
        output = "\n\n".join(entries)
        if len(output) < 1900:
            await msg.reply(f"\n{output}")
        else:
            for entry in entries:
                await msg.reply(f"\n{entry}\n\n")

    async def cancel(self, msg: Any, args: Sequence[str]) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        if not args:
            await msg.reply("This command needs one or more ID's. You'll find the ID's by using `!listreminders`.")
            return
        play_channel = await self._repository.get_play_channel(msg.guild.id, msg.channel.id, msg.author.id)
        folder_id = await self._repository.ensure_user_folder(msg.guild.id, play_channel, msg.author.id)
        await self._persistence.cancel_for_gm(
            str(msg.author.id), str(play_channel), set(args), str(folder_id)
        )
        await msg.reply(f"{len(args)} reminder cancellations were requested.")

    async def _append_gm_records(self, folder_id: str, reminders: Sequence[dict[str, Any]]) -> None:
        record = await self._repository.find_string("gmReminders", folder_id)
        current = await self._repository.get_string(str(record["_id"])) if record else ""
        added = "\n".join(serialize_reminder(reminder) for reminder in reminders)
        content = f"{current}\n{added}" if current else added
        await self._repository.set_string("gmReminders", folder_id, content)

    @staticmethod
    def _format_date(value: datetime) -> str:
        return value.strftime("%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)")

    @staticmethod
    def _in_guild(msg: Any) -> bool:
        return getattr(msg, "guild", None) is not None
