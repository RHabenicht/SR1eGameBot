import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sr1egamebot.commands import CommandDispatcher


class CommandDispatcherTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.initiative = SimpleNamespace(**{
            name: AsyncMock() for name in (
                "roll", "set_gm", "set_players", "add_players", "list_players",
                "remove_players", "clear_players", "set_init", "set_npcs", "add_npcs",
                "list_npcs", "remove_npcs", "clear_npcs",
            )
        })
        self.macros = SimpleNamespace(**{
            name: AsyncMock() for name in ("save", "roll", "remove", "list")
        })
        self.scenes = SimpleNamespace(**{
            name: AsyncMock() for name in (
                "check_channel", "set_channel", "set_scene", "delete_scenes", "get_scene", "list_scenes"
            )
        })
        self.reminders = SimpleNamespace(**{
            name: AsyncMock() for name in ("list", "add", "cancel")
        })
        self.ammo = SimpleNamespace(command=AsyncMock())
        self.dispatcher = CommandDispatcher(
            initiative=self.initiative, macros=self.macros, scenes=self.scenes,
            reminders=self.reminders, ammo=self.ammo,
        )

    def message(self, content):
        return SimpleNamespace(content=content, author=SimpleNamespace(bot=False, id="user"))

    async def test_prefix_aliases_route_to_services(self):
        msg = self.message("!setplayers <@123> <@456>")
        await self.dispatcher.on_message(msg)
        self.initiative.set_players.assert_awaited_once_with(msg, ["<@123>", "<@456>"])

        msg = self.message("!setnpcinits 1 5 guard")
        await self.dispatcher.on_message(msg)
        self.initiative.set_npcs.assert_awaited_once_with(msg, ["1", "5", "guard"])

        msg = self.message("!addreminders 2030-01-01T00:00:00Z 30m")
        await self.dispatcher.on_message(msg)
        self.reminders.add.assert_awaited_once_with(msg, ["2030-01-01T00:00:00Z", "30m"])

    async def test_disabled_admin_commands_and_non_prefix_messages_are_ignored(self):
        for command in ("open", "showcache", "clearcache"):
            await self.dispatcher.on_message(self.message(f"!{command}"))
        await self.dispatcher.on_message(self.message("showcache"))
        for service in (self.initiative, self.macros, self.scenes, self.reminders, self.ammo):
            for method in vars(service).values():
                if hasattr(method, "assert_not_awaited"):
                    method.assert_not_awaited()

    async def test_dice_reaction_ignores_bots_and_non_dice_emojis(self):
        msg = self.message("!4!")
        await self.dispatcher.on_reaction_add(
            SimpleNamespace(emoji=SimpleNamespace(name="🎲"), message=msg),
            SimpleNamespace(bot=True),
        )
        await self.dispatcher.on_reaction_add(
            SimpleNamespace(emoji=SimpleNamespace(name="✅"), message=msg),
            SimpleNamespace(bot=False),
        )
        self.assertEqual(self.macros.roll.await_count, 0)


if __name__ == "__main__":
    unittest.main()
