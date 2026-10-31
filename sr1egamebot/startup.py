"""Startup sequencing with readiness checks and best-effort cleanup."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class StartupError(RuntimeError):
    def __init__(self, stage: str, cause: BaseException) -> None:
        super().__init__(f"{stage} failed. Check configuration and service availability.")
        self.stage = stage
        self.__cause__ = cause


async def start_bot(
    *,
    client: Any,
    token: str,
    connect_database: Callable[[], Awaitable[None]],
    initialize: Callable[[], Awaitable[None]],
    close_database: Callable[[], Awaitable[None]],
    stop_reminders: Callable[[], Any] = lambda: None,
) -> asyncio.Task[None]:
    """Connect storage, initialize state, and return after Discord is ready.

    The returned task owns the long-running gateway connection and must be
    awaited by the application entry point.
    """
    stage = "MongoDB connection"
    connection_task: asyncio.Task[None] | None = None
    try:
        await connect_database()
        stage = "Database initialization"
        await initialize()
        stage = "Discord login"
        connection_task = asyncio.create_task(client.start(token))
        ready_task = asyncio.create_task(client.wait_until_ready())
        stage = "Discord readiness"
        done, _ = await asyncio.wait(
            (connection_task, ready_task), return_when=asyncio.FIRST_COMPLETED
        )
        if connection_task in done:
            ready_task.cancel()
            await connection_task  # Surface early login/connect failures.
            raise RuntimeError("Discord connection stopped before readiness.")
        ready_task.result()
        return connection_task
    except BaseException as cause:
        if connection_task is not None and not connection_task.done():
            connection_task.cancel()
        for cleanup in (stop_reminders, client.close, close_database):
            try:
                result = cleanup()
                if asyncio.iscoroutine(result):
                    await result
            except BaseException:
                pass
        if isinstance(cause, asyncio.CancelledError):
            raise
        raise StartupError(stage, cause) from cause
