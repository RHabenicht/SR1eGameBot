"""Command line entry point."""

from __future__ import annotations

import asyncio
import sys

from .config import ConfigurationError
from .discord_app import run_bot
from .startup import StartupError


def main() -> None:
    try:
        asyncio.run(run_bot())
    except (ConfigurationError, StartupError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
