"""User-scoped option files and the legacy account preference commands."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .repository import LegacyRepository


class UserOptions:
    def __init__(self, repository: LegacyRepository) -> None:
        self._repository = repository

    async def get(self, user_id: str | int, option: str) -> str | None:
        root = await self._repository.ensure_folder("UserData", encrypted=False)
        options = await self._repository.ensure_folder("options", str(root), encrypted=False)
        user = await self._repository.ensure_folder(str(user_id), str(options))
        record = await self._repository.find_string(option, str(user))
        if record is None:
            return None
        return await self._repository.get_string(str(record["_id"]))

    async def set(self, user_id: str | int, option: str, value: str) -> None:
        root = await self._repository.ensure_folder("UserData", encrypted=False)
        options = await self._repository.ensure_folder("options", str(root), encrypted=False)
        user = await self._repository.ensure_folder(str(user_id), str(options))
        await self._repository.set_string(option, str(user), value)


class UserOptionCommands:
    def __init__(self, options: UserOptions, maintenance_status: str) -> None:
        self._options = options
        self._maintenance_status = maintenance_status

    async def skip_status(self, msg: Any) -> None:
        try:
            await self._options.set(msg.author.id, "skipStatusMsg", self._maintenance_status)
        except Exception:
            await msg.reply("Something went wrong. Try again.")
            return
        await msg.reply("Responses to your commands won't include status messages again until the message changes.")

    async def link(self, msg: Any, args: Sequence[str]) -> None:
        try:
            existing = await self._options.get(msg.author.id, "webLinkCode")
        except Exception:
            return
        if existing:
            await msg.reply("You've already linked this account to the website.")
        elif len(args) != 1 or len(args[0].split("/")) != 2:
            await msg.reply("Incorrect code input. Use the button on the website to copy the full code and command.")
        else:
            try:
                await self._options.set(msg.author.id, "webLinkCode", args[0])
            except Exception:
                return
            await msg.reply("Link code registered.")
