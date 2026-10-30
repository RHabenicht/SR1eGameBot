"""Shadowrun and Cyberpunk initiative rules and saved setup commands."""

from __future__ import annotations

import random
import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from functools import cmp_to_key
from typing import Any

from .dice import roll_dice
from .repository import LegacyRepository


INITIATIVE_RULES = {
    "init": ((10, 16, 22, 1000), (7, 14, 21, 0)),
    "initflip": ((10, 16, 22, 1000), (7, 14, 21, 0)),
    "init2": ((10, 20, 30, 40), (10, 20, 30, 40)),
    "init2flip": ((10, 20, 30, 40), (10, 20, 30, 40)),
    "init3": ((10, 20, 30, 40), (10, 20, 30, 40)),
    "init3flip": ((10, 20, 30, 40), (10, 20, 30, 40)),
    "initcp": ((1000, 2000, 3000, 4000), (0, 0, 0, 0)),
    "initcpr": ((1000, 2000, 3000, 4000), (0, 0, 0, 0)),
}


def initiative_values(dice: int, modifier: int, command: str,
                      randbelow: Callable[[int], int] = random.randrange) -> list[int]:
    """Roll a character's initiative and return its base and extra passes."""
    if dice < 0:
        raise ValueError("initiative dice cannot be negative")
    sides = 10 if command in ("initcp", "initcpr") else 6
    rolls = [randbelow(sides) + 1 for _ in range(dice)]
    total = sum(rolls) + modifier
    thresholds, deductions = INITIATIVE_RULES[command]
    phases = [total]
    for threshold, deduction in zip(thresholds, deductions):
        if total > threshold:
            phases.append(total - deduction)
    return phases


def roll_initiative_entries(players: Sequence[tuple[str, str, str]],
                            npcs: Sequence[tuple[str, str, str]], command: str,
                            randbelow: Callable[[int], int] = random.randrange) -> list[list[str]]:
    """Return display groups ordered by initiative score, then edition tiebreaks."""
    third_edition = command in ("init3", "init3flip")
    first_edition = command in ("init", "initflip")
    cyberpunk_red = command == "initcpr"
    entities = [(label, dice, mod) for label, dice, mod in players]
    entities.extend(npcs)
    passes: list[list[tuple[int, str, str, int]]] = []
    for label, dice_text, mod_text in entities:
        phases = initiative_values(int(dice_text), int(mod_text), command, randbelow)
        for pass_index, score in enumerate(phases):
            while len(passes) <= pass_index:
                passes.append([])
            passes[pass_index].append((score, label, mod_text, pass_index))

    if not third_edition:
        passes = [sum(passes, [])]
    groups: list[tuple[int, list[tuple[int, str, str, int]]]] = []
    for phase in passes:
        by_score: dict[int, list[tuple[int, str, str, int]]] = defaultdict(list)
        for entry in phase:
            by_score[entry[0]].append(entry)
        for score, tied in by_score.items():
            if score < 1 or score > 40:
                continue
            if cyberpunk_red:
                def compare(left: tuple[int, str, str, int], right: tuple[int, str, str, int]) -> int:
                    if left[2] != right[2]:
                        return int(right[2]) - int(left[2])
                    while True:
                        a, b = randbelow(10) + 1, randbelow(10) + 1
                        if a != b:
                            return b - a
                tied.sort(key=cmp_to_key(compare))
            else:
                tied.sort(key=lambda item: int(item[2]), reverse=True)
            groups.append((score, tied))

    groups.sort(key=lambda item: item[0], reverse=True)
    if first_edition:
        action_count: dict[str, int] = defaultdict(int)
        ordered: list[tuple[int, list[tuple[int, str, str, int]]]] = []
        for score, group in groups:
            group.sort(key=lambda item: (action_count[item[1]], -int(item[2])))
            for _score, label, _modifier, _phase in group:
                action_count[label] += 1
            ordered.append((score, group))
        groups = ordered
    if command.endswith("flip"):
        groups.reverse()
    return [
        [f"*[{score}]* {label} ({modifier})" for _, label, modifier, _ in entries]
        for score, entries in groups
    ]


def _mention_id(value: str) -> str:
    match = re.fullmatch(r"<@!?([0-9]+)>", value)
    return match.group(1) if match else value


def _modify_npc_input(args: Sequence[str]) -> list[str]:
    values = list(args)
    if values and len(values) % 2 == 0:
        fixed = []
        for index in range(0, len(values), 2):
            token = values[index].lower()
            if "d6+" in token:
                dice, modifier = token.split("d6+", 1)
                fixed.extend([dice, modifier, values[index + 1]])
        if fixed:
            values = fixed
    for index in range(0, len(values), 3):
        if index < len(values) and values[index].lower().endswith("d6"):
            values[index] = values[index][:-2]
        if index + 1 < len(values) and values[index + 1].startswith("+"):
            values[index + 1] = values[index + 1][1:]
    return values


def _valid_npc_input(args: Sequence[str]) -> bool:
    if len(args) % 3 != 0 or any("," in value for value in args):
        return False
    for index in range(0, len(args), 3):
        try:
            float(args[index])
            float(args[index + 1])
        except (ValueError, IndexError):
            return False
    return True


class InitiativeService:
    def __init__(self, repository: LegacyRepository,
                 add_status: Callable[[Any, str], Any] = lambda _msg, text: text,
                 roll_dice_fn: Callable[..., tuple[int, list[int]]] = roll_dice,
                 randbelow: Callable[[int], int] = random.randrange) -> None:
        self._repository = repository
        self._add_status = add_status
        self._roll_dice = roll_dice_fn
        self._randbelow = randbelow

    async def set_gm(self, msg: Any, args: Sequence[str]) -> None:
        if not await self._server_only(msg): return
        play = await self._play(msg)
        target = _mention_id(args[0]) if args else str(msg.author.id)
        if args and target == args[0]:
            await self._reply(msg, 'This command requires you to "@" people correctly.')
            return
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        await self._repository.set_string("gmWhoIsGM", str(folder), target)
        if target == str(msg.author.id):
            await self._reply(msg, f"You are now a GM in channel <#{play}>.")
        else:
            await self._reply(msg, f"Your GM is now <@{target}> in this channel.")

    async def set_players(self, msg: Any, args: Sequence[str]) -> None:
        if not await self._server_only(msg): return
        play = await self._play(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        content = ",".join(_mention_id(value) for value in args)
        await self._repository.set_string("gmPlayers", str(folder), content)
        await self._reply(msg, f" your group in channel <#{play}> is now {len(args)} players.")

    async def add_players(self, msg: Any, args: Sequence[str]) -> None:
        if not await self._server_only(msg): return
        if args and not args[0].startswith("<@"):
            await self._reply(msg, 'This command requires you to "@" people correctly.')
            return
        play = await self._play(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        record = await self._repository.find_string("gmPlayers", str(folder))
        current = await self._repository.get_string(str(record["_id"])) if record else ""
        players = [p for p in current.split(",") if p]
        players.extend(_mention_id(value) for value in args)
        await self._repository.set_string("gmPlayers", str(folder), ",".join(players))
        await self._reply(msg, f" you added {len(args)} players to your group in channel <#{play}>; now there are {len(players)}.")

    async def list_players(self, msg: Any) -> None:
        if not await self._server_only(msg): return
        play = await self._play(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        record = await self._repository.find_string("gmPlayers", str(folder))
        content = await self._repository.get_string(str(record["_id"])) if record else ""
        players = [p for p in content.split(",") if p]
        if not players:
            await self._reply(msg, f"You don't have a group in channel <#{play}> yet.")
        else:
            mentions = "\n".join(f":arrow_right: <@{player}>" for player in players)
            await self._reply(msg, f"Your group in channel <#{play}> is {len(players)} players strong: {mentions}")

    async def remove_players(self, msg: Any, args: Sequence[str]) -> None:
        if not await self._server_only(msg): return
        play = await self._play(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        record = await self._repository.find_string("gmPlayers", str(folder))
        content = await self._repository.get_string(str(record["_id"])) if record else ""
        remove = {_mention_id(value) for value in args}
        players = [player for player in content.split(",") if player and player not in remove]
        removed = len([p for p in content.split(",") if p in remove])
        await self._repository.set_string("gmPlayers", str(folder), ",".join(players))
        await self._reply(msg, f"You removed {removed} players. You now have {len(players)} players in channel <#{play}>.")

    async def clear_players(self, msg: Any) -> None:
        if not await self._server_only(msg): return
        play = await self._play(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        await self._repository.set_string("gmPlayers", str(folder), "")
        await self._reply(msg, f"Your group for channel <#{play}> was reset to 0 players.")

    async def set_init(self, msg: Any, args: Sequence[str]) -> None:
        if not await self._server_only(msg): return
        values = list(args)
        if len(values) == 1 and "d6+" in values[0].lower():
            values = values[0].lower().split("d6+", 1)
        if values and values[0].lower().endswith("d6"):
            values[0] = values[0][:-2]
        if len(values) == 2 and values[1].startswith("+"):
            values[1] = values[1][1:]
        if len(values) != 2:
            await self._reply(msg, ":no_entry_sign: Wrong number of options; it's two numbers separated by a space.\nFor example: **!setinit 1 5** for **1**d6 +**5**")
            return
        try:
            float(values[0]); float(values[1])
        except ValueError:
            await self._reply(msg, ":no_entry_sign: Wrong type of options; it should be two numbers separated by a space.\nFor example: **!setinit 1 5** for **1**d6 +**5**")
            return
        folder = await self._repository.ensure_user_folder(msg.guild.id, msg.channel.id, msg.author.id)
        content = " ".join(values)
        await self._repository.set_string("playerInit", str(folder), content)
        await self._reply(msg, f"Your initiative formula (in this channel) is now {values[0]}d6 +{values[1]}.")

    async def _npc_command(self, msg: Any, args: Sequence[str], replace: bool) -> None:
        if not await self._server_only(msg): return
        values = _modify_npc_input(args)
        if not _valid_npc_input(values):
            await self._reply(msg, "There was a problem.\n:no_entry_sign: Check the NPC formula and label format in **!help init**.")
            return
        play = await self._play(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        record = await self._repository.find_string("gmNPCInit", str(folder))
        existing = await self._repository.get_string(str(record["_id"])) if record else ""
        old = [] if not existing else existing.split(",")
        entries = [" ".join(values[i:i + 3]) for i in range(0, len(values), 3)]
        result = entries if replace else old + entries
        await self._repository.set_string("gmNPCInit", str(folder), ",".join(result))
        verb = "were reset, and you added" if replace else "now have"
        count = len(entries) if replace else len(result)
        await self._reply(msg, f"Your NPC's for this channel {verb} {count} NPC's.")

    async def set_npcs(self, msg: Any, args: Sequence[str]) -> None:
        await self._npc_command(msg, args, replace=True)

    async def add_npcs(self, msg: Any, args: Sequence[str]) -> None:
        await self._npc_command(msg, args, replace=False)

    async def list_npcs(self, msg: Any) -> None:
        if not await self._server_only(msg): return
        play = await self._play(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        record = await self._repository.find_string("gmNPCInit", str(folder))
        content = await self._repository.get_string(str(record["_id"])) if record else ""
        npcs = [row for row in content.split(",") if row]
        if not npcs:
            await self._reply(msg, "You have no NPC's configured in this channel yet.")
            return
        output = "Your NPC's inits in this channel are:"
        for row in npcs:
            dice, modifier, label = row.split(" ", 2)
            output += f"\n:arrow_right: {dice}d6 +{modifier} :label: {label}"
        await self._reply(msg, output)

    async def remove_npcs(self, msg: Any, args: Sequence[str]) -> None:
        if not await self._server_only(msg): return
        play = await self._play(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        record = await self._repository.find_string("gmNPCInit", str(folder))
        content = await self._repository.get_string(str(record["_id"])) if record else ""
        old = [row for row in content.split(",") if row]
        removal = _modify_npc_input(args)
        if removal and len(removal) % 3 == 0:
            labels = {removal[i + 2] for i in range(0, len(removal), 3)}
            full = {" ".join(removal[i:i+3]) for i in range(0, len(removal), 3)}
        else:
            labels = set(removal)
            full = set()
        kept = [row for row in old if row not in full and row.split(" ")[2] not in labels]
        removed = len(old) - len(kept)
        await self._repository.set_string("gmNPCInit", str(folder), ",".join(kept))
        await self._reply(msg, f"You removed {removed} NPC's. You now have {len(kept)} NPC's in channel <#{play}>.")

    async def clear_npcs(self, msg: Any) -> None:
        if not await self._server_only(msg): return
        play = await self._play(msg)
        folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        await self._repository.set_string("gmNPCInit", str(folder), "")
        await self._reply(msg, "You cleared your NPC initiative formulas for this channel.")

    async def roll(self, msg: Any, command: str) -> None:
        if not await self._server_only(msg): return
        if command not in INITIATIVE_RULES:
            await self._reply(msg, "Unknown initiative system.")
            return
        play = await self._play(msg)
        gm_folder = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        players_record = await self._repository.find_string("gmPlayers", str(gm_folder))
        player_ids = await self._repository.get_string(str(players_record["_id"])) if players_record else ""
        players = [player for player in player_ids.split(",") if player and player != " "]
        not_set_gm: list[str] = []
        not_set_init: list[str] = []
        ready_players: list[tuple[str, str, str]] = []
        for player_id in players:
            player_folder = await self._repository.find_user_folder(msg.guild.id, play, player_id)
            if player_folder is None:
                not_set_gm.append(player_id)
                not_set_init.append(player_id)
                continue
            gm_record = await self._repository.find_string("gmWhoIsGM", str(player_folder["_id"]))
            player_gm = await self._repository.get_string(str(gm_record["_id"])) if gm_record else ""
            if player_gm != str(msg.author.id):
                not_set_gm.append(player_id)
            init_record = await self._repository.find_string("playerInit", str(player_folder["_id"]))
            formula = await self._repository.get_string(str(init_record["_id"])) if init_record else ""
            if len(formula.split()) < 2:
                not_set_init.append(player_id)
            else:
                dice, modifier = formula.split()[:2]
                ready_players.append((f"<@{player_id}>", dice, modifier))

        npc_record = await self._repository.find_string("gmNPCInit", str(gm_folder))
        npc_content = await self._repository.get_string(str(npc_record["_id"])) if npc_record else ""
        npcs: list[tuple[str, str, str]] = []
        for row in npc_content.split(","):
            if row.strip():
                fields = row.split(" ")
                if len(fields) >= 3:
                    npcs.append((fields[2], fields[0], fields[1]))

        output = ""
        if not_set_gm:
            output += "Some players haven't set you as their gm yet:\n"
            output += "".join(f":no_entry_sign: <@{player}>\n" for player in not_set_gm)
        if not_set_init:
            if output: output += "and"
            output += "Some players haven't set their initiative formulas yet:\n"
            output += "".join(f":no_entry_sign: <@{player}>\n" for player in not_set_init)
        failed = bool(not_set_gm or not_set_init)
        if not players and not npcs:
            failed = True
            output += f" -- can't roll initiative: you have no players or NPC's in channel <#{play}>."
        elif failed:
            output += " -- Can't roll initiative: players aren't ready.\n:thinking: :bulb: See **!inithelp** or ask your GM how to get set up!"
        if not failed:
            output += "\n*[Roll]* Player or NPC (Mod)\n========================\n"
            groups = roll_initiative_entries(ready_players, npcs, command, self._randbelow)
            output += "\n".join("\n".join(group) for group in groups)
            if output and not output.endswith("\n"):
                output += "\n"
        if (players or npcs) and not failed:
            output += "========================\n"
        await self._reply(msg, output)

    async def _play(self, msg: Any) -> str:
        return await self._repository.get_play_channel(msg.guild.id, msg.channel.id, msg.author.id)

    async def _reply(self, msg: Any, text: str) -> None:
        await msg.reply(await _await(self._add_status(msg, text)))

    @staticmethod
    async def _server_only(msg: Any) -> bool:
        if getattr(msg, "guild", None) is not None:
            return True
        await msg.reply("This command doesn't work via DM. You must be in a server channel.")
        return False


async def _await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
