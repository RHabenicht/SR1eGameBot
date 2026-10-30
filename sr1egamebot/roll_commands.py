"""Prefix dice-command parsing and Discord response formatting."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .dice import roll_dice


_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


@dataclass(frozen=True, slots=True)
class RollSpec:
    dice: int
    rule_of_six: bool
    total: bool
    target_number: int
    opponent_dice: int | None
    opponent_rule_of_six: bool
    opponent_target_number: int | None
    modifier: int
    note: str


def _number(text: str) -> float | None:
    if not _NUMBER.fullmatch(text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _target_number(args: Sequence[str]) -> int:
    target = -1
    for index, token in enumerate(args):
        if token[:2].lower() != "tn":
            continue
        value = token[2:]
        parsed = _number(value)
        if parsed is None or parsed < 2:
            following = _number(args[index + 1]) if index + 1 < len(args) else None
            target = int(following) if following is not None and following > 1 else -1
        else:
            target = int(parsed)
    return target


def _opponent(args: Sequence[str]) -> tuple[int | None, bool, int | None]:
    dice: int | None = None
    rule_of_six = False
    target: int | None = None
    for index, token in enumerate(args):
        lowered = token.lower()
        if lowered.startswith("vs") and len(token) > 2 and not lowered.startswith("vs."):
            value = token[2:]
            if value.endswith("!"):
                rule_of_six = True
                value = value[:-1]
            try:
                dice = int(value)
            except ValueError:
                dice = 0
        elif lowered.startswith("otn"):
            value = token[3:]
            parsed = _number(value)
            if parsed is None or parsed < 2:
                following = _number(args[index + 1]) if index + 1 < len(args) else None
                target = int(following) if following is not None and following > 1 else -1
            else:
                target = int(parsed)
    return dice, rule_of_six, target


def _modifier(args: Sequence[str]) -> int:
    for token in args:
        if token[:1] not in ("+", "-"):
            continue
        value = _number(token)
        if value is not None and value.is_integer():
            return int(value)
    return 0


def parse_roll(segment: str) -> RollSpec:
    parts = segment.strip().split()
    if not parts:
        return RollSpec(0, False, False, -1, None, False, None, 0, "")
    command = parts[0]
    if command.startswith("!"):
        command = command[1:]
    args = parts[1:]
    is_test = command.endswith("!")
    is_total = not is_test and command.lower().endswith("t")
    number_text = command[:-1] if is_test or is_total else command
    try:
        number = int(number_text)
    except ValueError:
        number = 0
    target = _target_number(args)
    opponent_dice, opponent_test, opponent_target = _opponent(args)
    note = " ".join([command, *args])
    if note:
        note = f"({note})"
    elif target > 0:
        note = f"(TN{target})"
    return RollSpec(
        dice=number,
        rule_of_six=is_test,
        total=is_total,
        target_number=target,
        opponent_dice=opponent_dice,
        opponent_rule_of_six=opponent_test,
        opponent_target_number=opponent_target,
        modifier=_modifier(args),
        note=note,
    )


async def handle_roll_command(
    msg: Any,
    cmd: str,
    args: Sequence[str],
    user: Any,
    override: str | None = None,
    *,
    add_status: Callable[[Any, str], Any] = lambda _msg, output: output,
    roll: Callable[..., tuple[int, list[int]]] = roll_dice,
    log: Callable[[str], Any] = lambda _message: None,
) -> None:
    """Handle a dice message, preserving its display, reroll, and semicolon behavior."""
    del cmd, args
    commands = (override if override is not None else msg.content).split(";")
    output = ""
    last_dice_count = 0

    for index, segment in enumerate(commands):
        if output:
            output += f"\nRoll #{index + 1}: "
        spec = parse_roll(segment)
        last_dice_count = spec.dice
        if spec.opponent_dice is not None and spec.opponent_target_number in (None, -1):
            response = await _await(add_status(
                msg,
                ":no_entry_sign: You ordered an opposed test without an opponent TN "
                "(the **otn** option).\nExample: **!6! tn4 vs5! *otn4***",
            ))
            await msg.reply(response)
            return

        successes, own_rolls = roll(spec.dice, spec.rule_of_six, spec.target_number)
        opponent_rolls: list[int] = []
        opponent_successes = 0
        if spec.opponent_dice is not None:
            opponent_successes, opponent_rolls = roll(
                spec.opponent_dice,
                spec.opponent_rule_of_six,
                int(spec.opponent_target_number),
            )

        if spec.total:
            total = sum(own_rolls) + spec.modifier
            output += f"[Total: {total}] | "
        if spec.opponent_dice is not None:
            if successes > opponent_successes:
                result = f"{successes - opponent_successes} net successes "
            elif successes == opponent_successes:
                result = "0 net successes"
            else:
                result = f"{opponent_successes - successes} *fewer* successes than the opponent! "
            output += (f"{user} rolled {result}({','.join(map(str, own_rolls))}) "
                       f"vs ({','.join(map(str, opponent_rolls))}) {spec.note}")
        else:
            success_text = f"{successes} successes " if successes > 0 else ""
            output += (f"{user}, you rolled {success_text}"
                       f"({','.join(map(str, own_rolls))}) {spec.note}")

    if last_dice_count > 0:
        output = await _await(add_status(msg, output))
        await msg.channel.send(output)
        log("🎲")
        await msg.add_reaction("🎲")


async def _await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
