import unittest
from collections import deque

from sr1egamebot.dice import roll_dice


def roller(values):
    rolls = deque(values)

    def randbelow(n):
        if not rolls:
            raise AssertionError("unexpected additional die roll")
        value = rolls.popleft()
        if not 0 <= value < n:
            raise AssertionError("fixture roll is out of range")
        return value

    return randbelow


class DiceTests(unittest.TestCase):
    def test_success_tests_sort_descending_and_count_target_numbers(self):
        successes, values = roll_dice(3, target_number=4, randbelow=roller([0, 3, 5]))
        self.assertEqual(successes, 2)
        self.assertEqual(values, [6, 4, 1])

    def test_rule_of_six_explodes_for_tests_over_six(self):
        successes, values = roll_dice(2, test=True, target_number=8,
                                      randbelow=roller([5, 3, 1]))
        self.assertEqual(successes, 1)
        self.assertEqual(values, [10, 2])

    def test_unexploded_roll_does_not_consume_extra_die(self):
        successes, values = roll_dice(1, target_number=6, randbelow=roller([5]))
        self.assertEqual((successes, values), (1, [6]))

    def test_negative_dice_count_is_rejected(self):
        with self.assertRaises(ValueError):
            roll_dice(-1)
