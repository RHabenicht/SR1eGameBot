"""Saved-roll commands stored in the existing encrypted strings collection."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from .repository import LegacyRepository


_DICE_MAIDEN = re.compile(r"(\d*)(D\d*)((?:[+*-](?:\d+|\([A-Z]*\)))*)(?:\+(D\d*))?", re.IGNORECASE)


class MacroService:
    def __init__(
        self,
        repository: LegacyRepository,
        roll_command: Callable[..., Awaitable[Any]],
        *,
        add_status: Callable[[Any, str], Any] = lambda _msg, text: text,
        log: Callable[[str], Any] = lambda _message: None,
    ) -> None:
        self._repository = repository
        self._roll_command = roll_command
        self._add_status = add_status
        self._log = log

    async def save(self, msg: Any, args: Sequence[str]) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        if len(args) < 2:
            await self._reply(msg, ":no_entry_sign: Not enough options. Needs a name followed by any valid dice roll command.")
            return
        folder = await self._repository.ensure_user_folder(
            msg.channel.guild.id, msg.channel.id, msg.author.id
        )
        macro_name, *roll_parts = args
        entry = f"{macro_name} {' '.join(roll_parts)}"
        saved = await self._repository.find_string("savedRolls", str(folder))
        lines = (await self._repository.get_string(str(saved["_id"]))).split("\n") if saved else []
        for index, line in enumerate(lines):
            if line.split(" ", 1)[0] == macro_name:
                lines[index] = entry
                break
        else:
            lines.append(entry)
        await self._repository.set_string("savedRolls", str(folder), "\n".join(lines))
        await self._reply(msg, f"You now have {len(lines)} roll macros saved.")
        self._log(f"🎲🎲 {msg.channel.guild.id}/{msg.channel.id}/{msg.author.id}")

    async def roll(self, msg: Any, args: Sequence[str], user: Any) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        joined = " ".join(args)
        if _DICE_MAIDEN.search(joined):
            self._log(f"Coexisting with Dice Maiden (by ignoring !roll {joined})")
            return
        if not args:
            await self._reply(msg, ":no_entry_sign: You didn't specify which macro I should roll.")
            return
        folder = await self._repository.ensure_user_folder(
            msg.channel.guild.id, msg.channel.id, msg.author.id
        )
        saved = await self._repository.find_string("savedRolls", str(folder))
        if saved is None:
            await self._reply(msg, " you don't have any saved macros in this channel yet.")
            return
        lines = (await self._repository.get_string(str(saved["_id"]))).split("\n")
        for line in lines:
            fields = line.split(" ")
            if fields and fields[0] == args[0]:
                command = fields[1] if len(fields) > 1 else ""
                if not command.startswith("!"):
                    command = f"!{command}"
                remaining = fields[2:]
                content = f"{command} {' '.join(remaining)}"
                await self._roll_command(msg, command, remaining, user, content)
                return

    async def remove(self, msg: Any, args: Sequence[str]) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        if not args:
            await self._reply(msg, ":no_entry_sign: You didn't specify which macro I should remove.")
            return
        folder = await self._repository.ensure_user_folder(
            msg.channel.guild.id, msg.channel.id, msg.author.id
        )
        saved = await self._repository.find_string("savedRolls", str(folder))
        if saved is None:
            await self._reply(msg, "You don't have any saved macros in this channel yet.")
            return
        lines = (await self._repository.get_string(str(saved["_id"]))).split("\n")
        content = await self._repository.get_string(str(saved["_id"]))
        if not content:
            await self._reply(msg, "You don't have any saved macros in this channel yet.")
            return
        index = next((i for i, line in enumerate(lines)
                      if line.split(" ", 1)[0] == args[0]), None)
        if index is None:
            await self._reply(msg, "That name didn't match any of your saved macros in this channel.")
            return
        del lines[index]
        await self._repository.set_string("savedRolls", str(folder), "\n".join(lines))
        await self._reply(msg, f"Removed the macro; you now have {len(lines)} macros saved in this channel.")

    async def list(self, msg: Any) -> None:
        if not self._in_guild(msg):
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        folder = await self._repository.ensure_user_folder(
            msg.channel.guild.id, msg.channel.id, msg.author.id
        )
        saved = await self._repository.find_string("savedRolls", str(folder))
        content = await self._repository.get_string(str(saved["_id"])) if saved else ""
        if not content:
            await self._reply(msg, "You don't have any saved macros in this channel yet.")
            return
        output = ""
        for line in content.split("\n"):
            fields = line.split(" ")
            name, roll = fields[0], " ".join(fields[1:])
            output += f"***{name}*** :arrow_right: {roll}\n"
        await self._reply(msg, f"You have the following macros in this channel:\n{output}")

    async def _reply(self, msg: Any, text: str) -> None:
        await msg.reply(await _await(self._add_status(msg, text)))

    @staticmethod
    def _in_guild(msg: Any) -> bool:
        return getattr(getattr(msg, "channel", None), "guild", None) is not None


async def _await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
