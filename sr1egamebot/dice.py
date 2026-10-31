"""Pure Shadowrun dice primitives, kept deterministic-test friendly."""

from __future__ import annotations

import random
from collections.abc import Callable

Roller = Callable[[int], int]


def roll_d6(explode: bool = False, randbelow: Roller = random.randrange) -> int:
    """Roll one d6; Rule of Six recursively adds another die above TN 6."""
    roll = randbelow(6) + 1
    if roll == 6 and explode:
        return roll + roll_d6(True, randbelow)
    return roll


def roll_dice(number: int, test: bool = False, target_number: int = -1,
              randbelow: Roller = random.randrange) -> tuple[int, list[int]]:
    """Return successes and descending individual rolls, matching the JS bot."""
    if number < 0:
        raise ValueError("number of dice cannot be negative")
    rolls = sorted((roll_d6(test, randbelow) for _ in range(number)), reverse=True)
    successes = sum(1 for value in rolls if target_number > -1 and value >= target_number)
    return successes, rolls
