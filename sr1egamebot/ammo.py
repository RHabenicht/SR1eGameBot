"""Weapon and ammunition tracking stored in the legacy string files."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .repository import LegacyRepository


def parse_ammo(content: str) -> list[dict[str, str]]:
    fields = ("qtyContainers", "containerType", "qtyRounds", "roundType", "maxRounds")
    result = []
    for line in content.split("\n"):
        values = line.split(",")
        if line and len(values) >= len(fields):
            result.append(dict(zip(fields, values[:len(fields)])))
    return result


def save_ammo(items: Sequence[dict[str, Any]]) -> str:
    lines = []
    for item in items:
        try:
            valid = (float(item["qtyContainers"]) > 0 and float(item["qtyRounds"]) > 0
                     and item.get("roundType") not in (None, "undefined"))
        except (TypeError, ValueError, KeyError):
            valid = False
        if valid:
            lines.append(",".join(str(item[key]) for key in (
                "qtyContainers", "containerType", "qtyRounds", "roundType", "maxRounds")))
    return "\n".join(lines)


def parse_guns(content: str) -> list[dict[str, str]]:
    fields = ("name", "maxROF", "ammoContainerType", "ammoCapacity", "ammoTypeLoaded", "ammoQtyLoaded", "ammoTypes")
    result = []
    for line in content.split("\n"):
        values = line.split(",")
        if line and len(values) >= len(fields):
            result.append(dict(zip(fields, values[:len(fields)])))
    return result


def save_guns(items: Sequence[dict[str, Any]]) -> str:
    return "\n".join(",".join(str(item[field]) for field in (
        "name", "maxROF", "ammoContainerType", "ammoCapacity", "ammoTypeLoaded", "ammoQtyLoaded", "ammoTypes"))
        for item in items)


def merge_ammo(existing: str, new: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = parse_ammo(existing)
    for item in items:
        if all(item[key] == str(new[key]) for key in ("containerType", "qtyRounds", "roundType", "maxRounds")):
            item["qtyContainers"] = str(float(item["qtyContainers"]) + float(new["qtyContainers"]))
            if item["qtyContainers"].endswith(".0"):
                item["qtyContainers"] = item["qtyContainers"][:-2]
            return items
    items.append(dict(new))
    return items


class AmmoService:
    def __init__(self, repository: LegacyRepository,
                 add_status: Callable[[Any, str], Any] = lambda _msg, text: text) -> None:
        self._repository = repository
        self._add_status = add_status

    async def command(self, msg: Any, args: Sequence[str]) -> None:
        if getattr(msg, "guild", None) is None:
            await msg.reply("This command doesn't work via DM. You must be in a server channel.")
            return
        if not args:
            await self._reply(msg, "Please see `!help ammo` for correct syntax.")
            return
        command = args[0].lower()
        actions = {
            "addgun": self._add_gun, "delgun": self._delete_gun,
            "addammo": self._add_ammo, "delammo": self._delete_ammo,
            "list": self._list, "fire": self._fire, "reload": self._reload,
        }
        action = actions.get(command)
        if action is not None:
            await action(msg, args)

    async def _add_gun(self, msg: Any, args: Sequence[str]) -> None:
        if len(args) < 5:
            await self._reply(msg, "Please see `!help ammo` for correct syntax.")
            return
        name, rof, container, capacity = args[1:5]
        folder, play = await self._context(msg)
        guns = await self._guns(folder)
        if any(gun["name"] == name for gun in guns):
            await self._reply(msg, f"You can't use the same name for multiple guns and you've already used the name **{name}**.")
            return
        gun = {"name": name, "maxROF": rof, "ammoContainerType": container,
               "ammoCapacity": capacity, "ammoTypeLoaded": "not loaded", "ammoQtyLoaded": "0",
               "ammoTypes": " ".join(args[5:])}
        guns.append(gun)
        await self._save_guns(folder, guns)
        await self._reply(msg, f"Gun added; you now have {len(guns)} guns in channel <#{play}>.")

    async def _delete_gun(self, msg: Any, args: Sequence[str]) -> None:
        folder, play = await self._context(msg)
        guns = await self._guns(folder)
        guns = [gun for gun in guns if not (len(args) > 1 and gun["name"] == args[1])]
        await self._save_guns(folder, guns)
        await self._reply(msg, f"Gun removed; you now have {len(guns)} guns in channel <#{play}>.")

    async def _add_ammo(self, msg: Any, args: Sequence[str]) -> None:
        if len(args) < 6:
            await self._reply(msg, "Please see `!help ammo` for correct syntax.")
            return
        ammo = {"qtyContainers": args[1], "containerType": args[2], "qtyRounds": args[3],
                "roundType": args[4], "maxRounds": args[5]}
        folder, play = await self._context(msg)
        items = merge_ammo(await self._read(folder, "ammoList"), ammo)
        await self._repository.set_string("ammoList", folder, save_ammo(items))
        await self._reply(msg, f"You added {ammo['qtyContainers']} {ammo['containerType']}s "
                          f"({ammo['qtyRounds']}/{ammo['maxRounds']} {ammo['roundType']}s) in channel <#{play}>.")

    async def _delete_ammo(self, msg: Any, args: Sequence[str]) -> None:
        if len(args) < 6:
            await self._reply(msg, "Please see `!help ammo` for correct syntax.")
            return
        folder, play = await self._context(msg)
        content = await self._read(folder, "ammoList")
        if not content:
            await self._reply(msg, f" you have no ammo to delete in channel <#{play}>.")
            return
        wanted = {"containerType": args[2], "qtyRounds": args[3], "roundType": args[4], "maxRounds": args[5]}
        items = parse_ammo(content)
        output = ""
        for item in items:
            if all(item[field] == value for field, value in wanted.items()):
                had = item["qtyContainers"]
                item["qtyContainers"] = str(float(item["qtyContainers"]) - float(args[1]))
                if item["qtyContainers"].endswith(".0"):
                    item["qtyContainers"] = item["qtyContainers"][:-2]
                if float(item["qtyContainers"]) < 0:
                    item["qtyContainers"] = "0"
                    output = f"You only had {had} of that ammo to begin with; they will be removed."
                else:
                    output = (f" {args[1]} {args[2]}s of {args[4]} (qty {args[3]}/{args[5]} max) "
                              f"were removed from channel <#{play}>.")
                break
        await self._repository.set_string("ammoList", folder, save_ammo(items))
        await self._reply(msg, output)

    async def _list(self, msg: Any, _args: Sequence[str]) -> None:
        folder, play = await self._context(msg)
        guns = await self._guns(folder)
        ammo = parse_ammo(await self._read(folder, "ammoList"))
        output = "\n***==[ GUNS ]==***\n"
        if not guns:
            output += f"You have no guns setup yet in channel <#{play}>.\n"
        else:
            for gun in guns:
                types = gun["ammoTypes"].replace(" ", "/")
                output += (f":arrow_right: **{gun['name']}** {gun['ammoContainerType']} ({gun['ammoCapacity']}), "
                           f"ROF: {gun['maxROF']}, Ammo type(s): {types}, ")
                if gun["ammoTypeLoaded"] == "not loaded":
                    output += "**Not loaded**\n"
                else:
                    output += f"Loaded with {gun['ammoQtyLoaded']} {gun['ammoTypeLoaded']}s\n"
        output += "***==[ AMMO ]==***\n"
        if not ammo:
            output += f"You have no ammo setup yet in channel <#{play}>.\n"
        else:
            nonempty = [item for item in ammo if float(item["qtyContainers"]) > 0 and float(item["qtyRounds"]) > 0]
            for item in nonempty:
                output += (f":arrow_right: {item['qtyContainers']} {item['containerType']}s of {item['roundType']} "
                           f"with {item['qtyRounds']} rounds (max {item['maxRounds']})\n")
            if not nonempty:
                output += "All your ammo containers are empty.\n"
        await self._reply(msg, output)

    async def _fire(self, msg: Any, args: Sequence[str]) -> None:
        if len(args) < 3:
            await self._reply(msg, "Please see `!help ammo` for correct syntax.")
            return
        name, shots = args[1], args[2]
        folder, play = await self._context(msg)
        guns = await self._guns(folder)
        gun = next((g for g in guns if g["name"] == name), None)
        if gun is None:
            await self._reply(msg, f"I couldn't find a gun named {name} in your list of guns in channel <#{play}>.")
            return
        if gun["ammoTypeLoaded"] == "not loaded":
            await self._reply(msg, f"Weapon **{name}** is not loaded!")
            return
        try:
            shot_count, loaded, max_rof = float(shots), float(gun["ammoQtyLoaded"]), float(gun["maxROF"])
        except ValueError:
            await self._reply(msg, "Please see `!help ammo` for correct syntax.")
            return
        if max_rof < shot_count:
            await self._reply(msg, f"This gun's maximum rate of fire is only {gun['maxROF']}. Try firing again with a valid number of shots.")
            return
        if loaded < shot_count:
            output = f"You fired {gun['ammoQtyLoaded']} {gun['ammoTypeLoaded']}s from your {name} before the weapon clicked empty."
            gun["ammoQtyLoaded"], gun["ammoTypeLoaded"] = "0", "not loaded"
        else:
            output = f"You fired {shots} {gun['ammoTypeLoaded']}s from your {name}."
            remaining = loaded - shot_count
            gun["ammoQtyLoaded"] = str(int(remaining) if remaining.is_integer() else remaining)
        await self._save_guns(folder, guns)
        await self._reply(msg, output)

    async def _reload(self, msg: Any, args: Sequence[str]) -> None:
        if len(args) < 2:
            await self._reply(msg, " you need to specify a weapon to reload.")
            return
        name = args[1]
        ammo_type = args[2] if len(args) > 2 else None
        folder, play = await self._context(msg)
        ammo = parse_ammo(await self._read(folder, "ammoList"))
        guns = await self._guns(folder)
        if not guns:
            await self._reply(msg, "You have no gun to reload."); return
        if not ammo:
            await self._reply(msg, "You have no ammo to reload with."); return
        gun = next((g for g in guns if g["name"].lower() == name.lower()), None)
        if gun is None:
            await self._reply(msg, f"The gun name {name} did not match any gun you have setup in channel <#{play}>."); return
        compatible = [a for a in ammo if a["containerType"] == gun["ammoContainerType"]
                      and a["maxRounds"] == gun["ammoCapacity"]
                      and a["roundType"] in gun["ammoTypes"].split()
                      and float(a["qtyRounds"]) > 0 and float(a["qtyContainers"]) > 0]
        if not compatible:
            await self._reply(msg, "You have no ammo compatible with this gun."); return
        types = {item["roundType"] for item in compatible}
        if ammo_type is None and len(types) > 1:
            await self._reply(msg, "Multiple ammo entries with different round types are compatible with this gun, so you must specify which round type you want to reload.")
            return
        if ammo_type is not None:
            compatible = [item for item in compatible if item["roundType"] == ammo_type]
            if not compatible:
                await self._reply(msg, "You have no ammo compatible with this gun using that round type."); return
        chosen = max(compatible, key=lambda item: float(item["qtyRounds"]))
        loaded_type = chosen["roundType"]
        loaded_rounds = chosen["qtyRounds"]
        chosen["qtyContainers"] = str(float(chosen["qtyContainers"]) - 1)
        if chosen["qtyContainers"].endswith(".0"):
            chosen["qtyContainers"] = chosen["qtyContainers"][:-2]
        if gun["ammoTypeLoaded"] != "not loaded":
            partial = {"qtyContainers": "1", "containerType": gun["ammoContainerType"],
                       "qtyRounds": gun["ammoQtyLoaded"], "roundType": gun["ammoTypeLoaded"],
                       "maxRounds": gun["ammoCapacity"]}
            ammo = merge_ammo(save_ammo(ammo), partial)
            chosen = next(item for item in ammo if item["roundType"] == partial["roundType"]
                          and item["containerType"] == partial["containerType"]
                          and item["maxRounds"] == partial["maxRounds"]
                          and item["qtyRounds"] == partial["qtyRounds"])
            chosen["qtyContainers"] = str(float(chosen["qtyContainers"]) - 1)
            if chosen["qtyContainers"].endswith(".0"):
                chosen["qtyContainers"] = chosen["qtyContainers"][:-2]
        gun["ammoTypeLoaded"] = loaded_type
        gun["ammoQtyLoaded"] = loaded_rounds
        await self._save_guns(folder, guns)
        await self._repository.set_string("ammoList", folder, save_ammo(ammo))
        await self._reply(msg, "Your weapon was reloaded.")

    async def _context(self, msg: Any) -> tuple[str, str]:
        play = await self._repository.get_play_channel(msg.guild.id, msg.channel.id, msg.author.id)
        folder_id = await self._repository.ensure_user_folder(msg.guild.id, play, msg.author.id)
        return str(folder_id), str(play)

    async def _guns(self, folder: str) -> list[dict[str, str]]:
        return parse_guns(await self._read(folder, "gunList"))

    async def _read(self, folder: str, filename: str) -> str:
        record = await self._repository.find_string(filename, folder)
        return await self._repository.get_string(str(record["_id"])) if record else ""

    async def _save_guns(self, folder: str, guns: Sequence[dict[str, Any]]) -> None:
        await self._repository.set_string("gunList", folder, save_guns(guns))

    async def _reply(self, msg: Any, text: str) -> None:
        value = self._add_status(msg, text)
        if hasattr(value, "__await__"):
            value = await value
        await msg.reply(value)
