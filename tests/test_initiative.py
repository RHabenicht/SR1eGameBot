import unittest
from collections import deque
from types import SimpleNamespace

from test_storage import MemoryStore
from sr1egamebot.crypto_compat import AESCipher
from sr1egamebot.initiative import (
    InitiativeService, _modify_npc_input, initiative_values, roll_initiative_entries,
)
from sr1egamebot.repository import LegacyRepository


class InitiativeRulesTests(unittest.TestCase):
    def test_first_edition_extra_passes_use_seven_point_decrements(self):
        values = deque([5, 4, 5])
        def die(sides): return values.popleft()
        phases = initiative_values(2, 4, "init", die)
        self.assertEqual(phases, [15, 8])

    def test_second_and_third_edition_thresholds_and_flipped_order(self):
        values = deque([5, 5, 0, 0])
        def die(sides): return values.popleft()
        third = roll_initiative_entries([("<@a>", "2", "15"), ("<@b>", "2", "0")], [], "init3", die)
        self.assertEqual([int(line.split("]")[0][2:]) for group in third for line in group], [27, 17, 7, 2])
        values = deque([5, 5, 0, 0])
        flipped = roll_initiative_entries([("<@a>", "2", "15"), ("<@b>", "2", "0")], [], "init3flip", lambda sides: values.popleft())
        self.assertTrue(flipped[0][0].startswith("*[2]*"))

    def test_reaction_modifier_orders_tied_entries_and_npc_input_formats(self):
        values = deque([5, 2])
        entries = roll_initiative_entries([("<@a>", "1", "2"), ("<@b>", "1", "5")], [], "init2", lambda sides: values.popleft())
        self.assertEqual(entries[0], ["*[8]* <@b> (5)", "*[8]* <@a> (2)"])
        self.assertEqual(_modify_npc_input(["1d6+5", "thug"]), ["1", "5", "thug"])
        self.assertEqual(_modify_npc_input(["1d6", "+5", "thug"]), ["1", "5", "thug"])


class InitiativeCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = LegacyRepository(
            MemoryStore(), AESCipher(bytes([7]) * 32, bytes([8]) * 16)
        )
        rolls = deque([5, 4, 5])
        self.service = InitiativeService(self.repository, randbelow=lambda sides: rolls.popleft())

    def message(self, author="gm", channel="play"):
        replies = []
        async def reply(value): replies.append(value)
        msg = SimpleNamespace(
            guild=SimpleNamespace(id="server"), channel=SimpleNamespace(id=channel),
            author=SimpleNamespace(id=author), reply=reply,
        )
        return msg, replies

    async def test_setup_records_players_npcs_and_rolls_initiative(self):
        gm, replies = self.message(author="100")
        await self.service.set_players(gm, ["<@200>"])
        await self.service.set_gm(gm, [])
        await self.service.set_init(gm, ["1", "4"])
        # A player's GM link and initiative formula are stored in that player's folder.
        player, _ = self.message("200")
        await self.service.set_gm(player, ["<@100>"])
        await self.service.set_init(player, ["2", "4"])
        await self.service._npc_command(gm, ["1d6+3", "guard"], replace=True)
        await self.service.roll(gm, "init")
        self.assertIn("*[15]* <@200> (4)", replies[-1])
        self.assertIn("*[9]* guard (3)", replies[-1])

    async def test_unready_player_blocks_the_roll_and_dm_is_rejected(self):
        gm, replies = self.message(author="100")
        await self.service.set_players(gm, ["<@200>"])
        await self.service.roll(gm, "init3")
        self.assertIn("players aren't ready", replies[-1])

        dm, dm_replies = self.message()
        dm.guild = None
        await self.service.list_players(dm)
        self.assertIn("doesn't work via DM", dm_replies[0])
