import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from test_storage import MemoryStore
from sr1egamebot.crypto_compat import AESCipher
from sr1egamebot.reminders import (
    ReminderCommandService, ReminderManager, ReminderService,
    parse_datetime, parse_reminder_records, serialize_reminder,
)
from sr1egamebot.repository import LegacyRepository


class ReminderTests(unittest.IsolatedAsyncioTestCase):
    def test_parses_legacy_and_iso_dates_and_preserves_record_fields(self):
        legacy = "Fri Oct 30 2026 12:00:00 GMT+0000 (Coordinated Universal Time)"
        parsed = parse_datetime(legacy)
        self.assertEqual(parsed, datetime(2026, 10, 30, 12, tzinfo=timezone.utc))
        self.assertEqual(parse_datetime("2026-10-30T12:00:00Z"), parsed)
        reminder = {
            "shortID": "abc123", "id": "deadbeef", "sessionTimeDateF": "2026-10-30T12:00:00Z",
            "dateTime": legacy, "timeStamp": "1793361600000", "gmID": "gm-1",
            "userFolderID": "507f1f77bcf86cd799439011", "playChannelID": "channel-1",
            "playersString": "player-1 player-2",
        }
        serialized = serialize_reminder(reminder)
        restored = parse_reminder_records(serialized)
        self.assertEqual(restored[0]["shortID"], "abc123")
        self.assertEqual(restored[0]["smallID"], "abc123")
        self.assertEqual(restored[0]["playersString"], "player-1 player-2")

    async def test_restores_overdue_reminder_and_cancels_future_timer(self):
        delivered, errors = [], []
        async def deliver(reminder):
            delivered.append(reminder["shortID"])
            raise RuntimeError("delivery unavailable")
        due = datetime.now(timezone.utc) - timedelta(seconds=1)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        def row(short_id, when):
            timestamp = int(when.timestamp() * 1000)
            return {
                "shortID": short_id, "id": short_id, "sessionTimeDateF": when.isoformat(),
                "dateTime": when.isoformat(), "timeStamp": str(timestamp), "gmID": "gm",
                "userFolderID": "folder", "playChannelID": "channel", "playersString": "player",
            }
        payload = "\n".join(map(serialize_reminder, [row("due", due), row("future", future)]))
        manager = ReminderManager(deliver, errors.append)
        manager.restore(payload)
        manager.start()
        await asyncio.sleep(0.02)
        self.assertEqual(delivered, ["due"])
        self.assertEqual(len(errors), 1)
        manager.stop()

    async def test_add_persists_legacy_files_and_restores_without_production_access(self):
        repo = LegacyRepository(MemoryStore(), AESCipher(bytes([7]) * 32, bytes([8]) * 16))
        root_id = await repo.create_folder("UserData", encrypted=False)
        reminder_root = await repo.ensure_folder("reminders", str(root_id), encrypted=False)
        user_folder = await repo.ensure_user_folder("server", "channel", "gm")
        await repo.set_string("gmPlayers", str(user_folder), "player-1,player-2")
        delivered = []
        manager = ReminderManager(lambda r: _deliver(delivered, r))
        manager.start()
        store = ReminderService(repo, manager, lambda: str(reminder_root))
        command = ReminderCommandService(repo, manager, store)
        msg, replies = _message()
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        await command.add(msg, [future, "30m", "1d"])
        self.assertEqual(replies, ["2 reminders added. **NOTE:** Reminders are now based on GMT+0."])
        active = await repo.find_string("activeReminders", str(reminder_root))
        records = parse_reminder_records(await repo.get_string(str(active["_id"])))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["playersString"], "player-1 player-2")

        gm_file = await repo.find_string("gmReminders", str(user_folder))
        second_manager = ReminderManager(lambda r: _deliver(delivered, r))
        restored_store = ReminderService(repo, second_manager, lambda: str(reminder_root))
        restored = await restored_store.restore()
        self.assertEqual(len(restored), 2)
        self.assertEqual(restored[0]["shortID"], records[0]["shortID"])
        self.assertTrue(gm_file)
        manager.stop()

    async def test_successful_delivery_removes_active_and_gm_records(self):
        repo = LegacyRepository(MemoryStore(), AESCipher(bytes([7]) * 32, bytes([8]) * 16))
        root_id = await repo.create_folder("UserData", encrypted=False)
        reminder_root = await repo.ensure_folder("reminders", str(root_id), encrypted=False)
        user_folder = await repo.ensure_user_folder("server", "channel", "gm")
        now = datetime.now(timezone.utc) - timedelta(seconds=1)
        reminder = {
            "shortID": "due123", "id": "delivery-id", "sessionTimeDateF": now.isoformat(),
            "dateTime": now.isoformat(), "timeStamp": str(int(now.timestamp() * 1000)),
            "gmID": "gm", "userFolderID": str(user_folder), "playChannelID": "channel",
            "playersString": "player",
        }
        payload = serialize_reminder(reminder)
        await repo.set_string("activeReminders", str(reminder_root), payload)
        await repo.set_string("gmReminders", str(user_folder), payload)
        delivered = []
        manager = ReminderManager(lambda r: _deliver(delivered, r))
        store = ReminderService(repo, manager, lambda: str(reminder_root))
        manager.set_on_delivered(store.complete)
        await store.restore()
        manager.start()
        await asyncio.sleep(0.03)
        manager.stop()
        self.assertEqual([item["shortID"] for item in delivered], ["due123"])
        for name, folder in (("activeReminders", str(reminder_root)),
                             ("gmReminders", str(user_folder))):
            record = await repo.find_string(name, folder)
            self.assertEqual(await repo.get_string(str(record["_id"])), "")


def _message():
    replies = []
    async def reply(value): replies.append(value)
    msg = SimpleNamespace(guild=SimpleNamespace(id="server"), channel=SimpleNamespace(id="channel"),
                          author=SimpleNamespace(id="gm"), reply=reply)
    return msg, replies


async def _deliver(target, reminder):
    target.append(reminder)
