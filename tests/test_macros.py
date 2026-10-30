import unittest
from types import SimpleNamespace

from test_storage import MemoryStore
from sr1egamebot.crypto_compat import AESCipher
from sr1egamebot.macros import MacroService
from sr1egamebot.repository import LegacyRepository


class MacroTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.repository = LegacyRepository(
            self.store, AESCipher(bytes([7]) * 32, bytes([8]) * 16)
        )
        self.rolls = []
        async def roll(*args):
            self.rolls.append(args)
        self.service = MacroService(self.repository, roll)

    def message(self, channel="channel-a", user="player-a", guild=True):
        replies = []
        async def reply(value):
            replies.append(value)
        msg = SimpleNamespace(
            author=SimpleNamespace(id=user),
            channel=SimpleNamespace(id=channel,
                guild=SimpleNamespace(id="server-a") if guild else None),
            reply=reply,
        )
        return msg, replies

    async def test_save_replace_list_and_remove_macros(self):
        msg, replies = self.message()
        await self.service.save(msg, ["pistols", "5!", "tn4"])
        await self.service.save(msg, ["pistols", "6!", "tn3"])
        await self.service.save(msg, ["stealth", "4", "tn5"])
        self.assertEqual(replies, [
            "You now have 1 roll macros saved.",
            "You now have 1 roll macros saved.",
            "You now have 2 roll macros saved.",
        ])

        await self.service.list(msg)
        self.assertIn("***pistols*** :arrow_right: 6! tn3", replies[-1])
        self.assertIn("***stealth*** :arrow_right: 4 tn5", replies[-1])
        await self.service.remove(msg, ["pistols"])
        self.assertEqual(replies[-1], "Removed the macro; you now have 1 macros saved in this channel.")

    async def test_macro_roll_dispatch_preserves_arguments_and_channel_scope(self):
        msg, _ = self.message(channel="channel-a")
        await self.service.save(msg, ["pistols", "5!", "tn4"])
        await self.service.roll(msg, ["pistols"], msg.author)
        self.assertEqual(self.rolls[0][1:], ("!5!", ["tn4"], msg.author, "!5! tn4"))

        other, replies = self.message(channel="channel-b")
        await self.service.roll(other, ["pistols"], other.author)
        self.assertEqual(replies, [" you don't have any saved macros in this channel yet."])

    async def test_dice_maiden_commands_are_ignored_and_dm_use_is_rejected(self):
        msg, replies = self.message()
        await self.service.roll(msg, ["2d6+4"], msg.author)
        self.assertEqual(replies, [])
        self.assertEqual(self.rolls, [])

        dm, dm_replies = self.message(guild=False)
        await self.service.save(dm, ["pistols", "5!"])
        self.assertEqual(dm_replies, ["This command doesn't work via DM. You must be in a server channel."])
