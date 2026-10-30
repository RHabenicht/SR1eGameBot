import unittest
from types import SimpleNamespace

from sr1egamebot.help import HelpService
from sr1egamebot.help_texts import HELP_MESSAGES


class HelpServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = HelpService(lambda _msg, text: text + "\nStatus")

    async def test_all_existing_help_topics_are_available(self):
        self.assertEqual(set(HELP_MESSAGES), {
            "index", "main", "init", "scene", "macros", "gmscreen", "reminders", "ammo", "troubleshoot"
        })
        for topic in HELP_MESSAGES:
            msg, replies = _message()
            await self.service.command(msg, "help", [topic])
            self.assertEqual(len(replies), len(HELP_MESSAGES[topic]))
            self.assertTrue(replies[-1].endswith("\nStatus"))
            self.assertNotIn("Patreon", "\n".join(replies))

    async def test_legacy_inithelp_alias_and_unknown_topic_use_expected_pages(self):
        msg, replies = _message()
        await self.service.command(msg, "inithelp", [])
        self.assertEqual(replies[0], HELP_MESSAGES["init"][0])

        msg, replies = _message()
        await self.service.command(msg, "help", ["not-a-topic"])
        self.assertEqual(replies[0], HELP_MESSAGES["index"][0] + "\nStatus")


def _message():
    replies = []
    async def reply(text): replies.append(text)
    return SimpleNamespace(reply=reply), replies


if __name__ == "__main__":
    unittest.main()
