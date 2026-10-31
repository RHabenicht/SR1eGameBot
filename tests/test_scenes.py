import unittest
from types import SimpleNamespace

from test_storage import MemoryStore
from sr1egamebot.crypto_compat import AESCipher
from sr1egamebot.repository import LegacyRepository
from sr1egamebot.scenes import SceneService


class SceneTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = LegacyRepository(
            MemoryStore(), AESCipher(bytes([7]) * 32, bytes([8]) * 16)
        )
        self.sent_to_play_channel = []
        destination = SimpleNamespace(send=lambda text: _append(self.sent_to_play_channel, text))
        self.client = SimpleNamespace(get_channel=lambda channel_id: destination)
        self.service = SceneService(self.repository)

    def message(self, channel="gm-screen", user="gm"):
        replies = []
        async def reply(value): replies.append(value)
        return SimpleNamespace(
            guild=SimpleNamespace(id="server-a"),
            channel=SimpleNamespace(id=channel),
            author=SimpleNamespace(id=user),
            client=self.client,
            reply=reply,
        ), replies

    async def test_scene_commands_use_configured_play_channel_and_persist_format(self):
        msg, replies = self.message()
        await self.service.set_channel(msg, ["<#123456789012345678>"])
        self.assertIn("Play channel is now set to <#123456789012345678>", replies[-1])
        await self.service.set_scene(msg, ["intro", "https://music.example/track", "The", "door", "opens."])
        self.assertIn("1 scenes in channel <#123456789012345678>", replies[-1])

        folder = await self.repository.find_user_folder("server-a", "123456789012345678", "gm")
        scene = await self.repository.find_string("gmScene_intro", str(folder["_id"]))
        self.assertEqual(await self.repository.get_string(str(scene["_id"])),
                         "intro\n|||\nhttps://music.example/track\n|||\nThe door opens.")
        index = await self.repository.find_string("gmSceneList", str(folder["_id"]))
        self.assertEqual(await self.repository.get_string(str(index["_id"])),
                         f'intro\n|||\n{scene["_id"]}\n|||||\n')

        await self.service.list_scenes(msg)
        self.assertIn("intro", replies[-1])
        await self.service.get_scene(msg, ["intro"])
        self.assertEqual(self.sent_to_play_channel,
                         ["The door opens.\n\nSoundtrack:\nhttps://music.example/track"])
        self.assertIn('Scene "intro" was just deployed', replies[-1])

    async def test_remove_and_check_channel(self):
        msg, replies = self.message()
        await self.service.set_scene(msg, ["one", "text"])
        await self.service.set_scene(msg, ["two", "text"])
        await self.service.delete_scenes(msg, ["one"])
        self.assertIn("1 scenes in channel <#gm-screen>", replies[-1])
        await self.service.check_channel(msg)
        self.assertIn("current play channel is set to <#gm-screen>", replies[-1])


def _append(target, value):
    target.append(value)
    async def done(): return None
    return done()
