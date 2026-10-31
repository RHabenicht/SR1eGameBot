"""Prefix command and reroll dispatch for the Python Discord client."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .ammo import AmmoService
from .help import HelpService
from .initiative import InitiativeService
from .macros import MacroService
from .reminders import ReminderCommandService
from .roll_commands import handle_roll_command
from .scenes import SceneService
from .user_options import UserOptionCommands


_INIT_COMMANDS = {
    "init", "init2", "init3", "initflip", "init2flip", "init3flip", "initcp", "initcpr",
}
_DISABLED_ADMIN_COMMANDS = {"open", "showcache", "clearcache"}


class CommandDispatcher:
    """Route the existing bang-prefix aliases to their Python service methods."""

    def __init__(self, *, initiative: InitiativeService, macros: MacroService,
                 scenes: SceneService, reminders: ReminderCommandService,
                 ammo: AmmoService, user_options: UserOptionCommands | None = None,
                 help_service: HelpService | None = None) -> None:
        self.initiative = initiative
        self.macros = macros
        self.scenes = scenes
        self.reminders = reminders
        self.ammo = ammo
        self.user_options = user_options
        self.help_service = help_service

    async def on_message(self, msg: Any, user: Any | None = None) -> None:
        content = getattr(msg, "content", "")
        if not content.startswith("!"):
            return
        parts = content[1:].split(" ")
        command = parts[0].lower() if parts else ""
        args = parts[1:]
        actor = user if user is not None else msg.author

        # These were removed from the maintained Node dispatcher because they
        # could expose process-wide cache data across servers.
        if command in _DISABLED_ADMIN_COMMANDS:
            return

        if command in _INIT_COMMANDS:
            await self.initiative.roll(msg, command)
        elif command == "setgm":
            await self.initiative.set_gm(msg, args)
        elif command in {"setp", "setplayers", "setplayer"}:
            await self.initiative.set_players(msg, args)
        elif command in {"addp", "addplayers", "addplayer"}:
            await self.initiative.add_players(msg, args)
        elif command in {"lp", "listplayers"}:
            await self.initiative.list_players(msg)
        elif command in {"rmp", "removeplayer", "removeplayers"}:
            await self.initiative.remove_players(msg, args)
        elif command in {"clrp", "clearplayers"}:
            await self.initiative.clear_players(msg)
        elif command in {"si", "seti", "setinit"}:
            await self.initiative.set_init(msg, args)
        elif command in {"setn", "setnpc", "setnpcs", "setnpcinits", "setnpcinit"}:
            await self.initiative.set_npcs(msg, args)
        elif command in {"addn", "addnpc", "addnpcs", "addnpcinits", "addnpcinit"}:
            await self.initiative.add_npcs(msg, args)
        elif command in {"ln", "listnpcs", "listnpcinits", "listnpcinit"}:
            await self.initiative.list_npcs(msg)
        elif command in {"rmn", "rmnpc", "rmnpcs", "removenpc", "removenpcs",
                         "removenpcinit", "removenpcinits"}:
            await self.initiative.remove_npcs(msg, args)
        elif command in {"clrn", "clearnpcinits", "clearnpcinit"}:
            await self.initiative.clear_npcs(msg)
        elif command == "save":
            await self.macros.save(msg, args)
        elif command == "roll":
            await self.macros.roll(msg, args, actor)
        elif command in {"removemacro", "rmm"}:
            await self.macros.remove(msg, args)
        elif command in {"lm", "listmacros"}:
            await self.macros.list(msg)
        elif command == "checkchannel":
            await self.scenes.check_channel(msg)
        elif command == "setchannel":
            await self.scenes.set_channel(msg, args)
        elif command == "setscene":
            await self.scenes.set_scene(msg, args)
        elif command == "delscene":
            await self.scenes.delete_scenes(msg, args)
        elif command == "getscene":
            await self.scenes.get_scene(msg, args)
        elif command == "listscenes":
            await self.scenes.list_scenes(msg)
        elif command == "listreminders":
            await self.reminders.list(msg)
        elif command in {"addreminder", "addreminders"}:
            await self.reminders.add(msg, args)
        elif command in {"cancelreminder", "cancelreminders"}:
            await self.reminders.cancel(msg, args)
        elif command == "ammo":
            await self.ammo.command(msg, args)
        elif command in {"help", "inithelp"} and self.help_service is not None:
            await self.help_service.command(msg, command, args)
        elif command in {"help", "inithelp"}:
            await self._unported(msg, "Help")
        elif command == "skipstatus" and self.user_options is not None:
            await self.user_options.skip_status(msg)
        elif command == "link" and self.user_options is not None:
            await self.user_options.link(msg, args)
        elif command in {"skipstatus", "link"}:
            await self._unported(msg, "User settings")
        else:
            await handle_roll_command(msg, command, args, actor)

    async def on_reaction_add(self, reaction: Any, user: Any) -> None:
        emoji = getattr(reaction, "emoji", "")
        name = getattr(emoji, "name", str(emoji))
        if name not in {"🎲", "game_die", ":game_die:"} or getattr(user, "bot", False):
            return
        msg = reaction.message
        if getattr(msg, "partial", False):
            msg = await msg.fetch()
        await self.on_message(msg, user)

    async def _unported(self, msg: Any, feature: str) -> None:
        await msg.reply(f"{feature} commands are not available in this Python port yet.")
