import unittest
from types import SimpleNamespace

from test_storage import MemoryStore
from sr1egamebot.crypto_compat import AESCipher
from sr1egamebot.repository import LegacyRepository
from sr1egamebot.user_options import UserOptionCommands, UserOptions


class UserOptionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = LegacyRepository(
            MemoryStore(), AESCipher(bytes([7]) * 32, bytes([8]) * 16)
        )
        self.options = UserOptions(self.repository)

    async def test_settings_use_the_legacy_userdata_options_tree(self):
        await self.options.set("123456789012345678", "webLinkCode", "alpha/beta")
        self.assertEqual(await self.options.get("123456789012345678", "webLinkCode"), "alpha/beta")
        root = await self.repository.find_folder("UserData", encrypted=False)
        options = await self.repository.find_folder("options", str(root["_id"]), encrypted=False)
        user = await self.repository.find_folder("123456789012345678", str(options["_id"]))
        record = await self.repository.find_string("webLinkCode", str(user["_id"]))
        self.assertTrue(record["encrypted"])

    async def test_skipstatus_and_link_feedback_matches_existing_behavior(self):
        commands = UserOptionCommands(self.options, "maintenance notice")
        msg, replies = _message()
        await commands.skip_status(msg)
        self.assertEqual(await self.options.get("gm", "skipStatusMsg"), "maintenance notice")
        self.assertIn("won't include status messages", replies[-1])

        await commands.link(msg, ["alpha/beta"])
        self.assertEqual(await self.options.get("gm", "webLinkCode"), "alpha/beta")
        self.assertEqual(replies[-1], "Link code registered.")
        await commands.link(msg, ["other/code"])
        self.assertEqual(replies[-1], "You've already linked this account to the website.")


def _message():
    replies = []
    async def reply(value): replies.append(value)
    return SimpleNamespace(author=SimpleNamespace(id="gm"), reply=reply), replies


if __name__ == "__main__":
    unittest.main()
