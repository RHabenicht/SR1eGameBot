"""Existing topic-based help responses."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .help_texts import HELP_MESSAGES


class HelpService:
    def __init__(self, add_status: Callable[[Any, str], Any] = lambda _msg, text: text) -> None:
        self._add_status = add_status

    async def command(self, msg: Any, command: str, args: Sequence[str]) -> None:
        if (args and args[0] == "2") or command == "inithelp":
            topic = "init"
        elif args and args[0] in HELP_MESSAGES:
            topic = args[0]
        else:
            topic = "index"

        messages = list(HELP_MESSAGES[topic])
        if messages:
            messages[-1] = await _await(self._add_status(msg, messages[-1]))
        for message in messages:
            await msg.reply(message)


async def _await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
