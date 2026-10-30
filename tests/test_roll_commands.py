import unittest
from collections import deque
from types import SimpleNamespace

from sr1egamebot.roll_commands import handle_roll_command, parse_roll


def roller(values):
    pool = deque(values)

    def roll(number, test, target):
        results = []
        for _ in range(number):
            first = pool.popleft()
            value = first
            while test and value % 6 == 0 and value > 0:
                value += pool.popleft()
            results.append(value)
        results.sort(reverse=True)
        return sum(1 for value in results if target > -1 and value >= target), results

    return roll


class RollCommandTests(unittest.IsolatedAsyncioTestCase):
    def make_message(self, text):
        sent, reactions, replies = [], [], []
        msg = SimpleNamespace(content=text,
                              channel=SimpleNamespace(send=lambda value: _append(sent, value)),
                              reply=lambda value: _append(replies, value),
                              add_reaction=lambda value: _append(reactions, value))
        return msg, sent, reactions, replies

    def test_parses_standard_target_total_and_opposed_syntax(self):
        ordinary = parse_roll("!5! tn4")
        self.assertEqual((ordinary.dice, ordinary.rule_of_six, ordinary.target_number), (5, True, 4))
        total = parse_roll("2t +3")
        self.assertEqual((total.dice, total.total, total.modifier), (2, True, 3))
        opposed = parse_roll("6! tn4 vs5! otn4")
        self.assertEqual((opposed.dice, opposed.target_number, opposed.opponent_dice,
                          opposed.opponent_rule_of_six, opposed.opponent_target_number),
                         (6, 4, 5, True, 4))

    async def test_total_and_semicolon_output_keep_current_conventions(self):
        msg, sent, reactions, _ = self.make_message("!2t +3; 1")
        await handle_roll_command(msg, "2t", ["+3"], "<@player>",
                                  roll=roller([2, 4, 1]))
        self.assertEqual(len(sent), 1)
        self.assertIn("[Total: 9]", sent[0])
        self.assertIn("Roll #2: <@player>, you rolled (1) (1)", sent[0])
        self.assertEqual(reactions, ["🎲"])

    async def test_opposed_roll_rejects_a_missing_opponent_target(self):
        msg, sent, _, replies = self.make_message("!2! tn4 vs2!")
        await handle_roll_command(msg, "2!", ["tn4", "vs2!"], "<@player>", roll=roller([]))
        self.assertEqual(sent, [])
        self.assertIn("opponent TN", replies[0])

    async def test_opposed_test_formats_net_successes(self):
        msg, sent, _, _ = self.make_message("!2 tn4 vs2 otn4")
        await handle_roll_command(msg, "", [], "<@player>", roll=roller([5, 3, 3, 1]))
        self.assertIn("1 net successes (5,3) vs (3,1)", sent[0])


def _append(target, value):
    target.append(value)
    async def done():
        return None
    return done()
