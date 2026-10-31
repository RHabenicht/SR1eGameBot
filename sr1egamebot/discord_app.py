"""discord.py client wiring for the currently ported command services."""

from __future__ import annotations

from typing import Any

from .ammo import AmmoService
from .commands import CommandDispatcher
from .config import BotConfig, load_config
from .crypto_compat import AESCipher
from .help import HelpService
from .initiative import InitiativeService
from .macros import MacroService
from .reminders import ReminderCommandService, ReminderManager, ReminderService, parse_datetime
from .repository import LegacyRepository
from .roll_commands import handle_roll_command
from .scenes import SceneService
from .startup import start_bot
from .storage import MongoStore
from .user_options import UserOptionCommands, UserOptions


def _make_discord_client() -> Any:
    import discord

    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.message_content = True
    intents.reactions = True
    intents.dm_messages = True
    return discord.Client(intents=intents)


async def run_bot(config: BotConfig | None = None, client: Any | None = None) -> None:
    """Run the bot after storage initialization and Discord readiness."""
    settings = config or load_config()
    discord_client = client or _make_discord_client()
    store = MongoStore(settings.db_url)
    repository = LegacyRepository(
        store, AESCipher(settings.crypto_key, settings.crypto_vector)
    )
    reminder_root: str | None = None

    async def deliver(reminder: dict[str, Any]) -> None:
        when = parse_datetime(reminder["sessionTimeDateF"])
        session_date = when.strftime("%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)")
        gm = await discord_client.fetch_user(int(reminder["gmID"]))
        for player_id in reminder["playersString"].split():
            player = await discord_client.fetch_user(int(player_id))
            try:
                await player.send(
                    f"This is a reminder of your upcoming game at {session_date} "
                    f"with GM **{gm.name}**."
                )
            except Exception:
                # The Node worker consumed DM send failures and still removed
                # the scheduled reminder after attempting delivery.
                continue

    manager = ReminderManager(deliver)
    persistence = ReminderService(repository, manager, lambda: reminder_root or "")
    manager.set_on_delivered(persistence.complete)
    initiative = InitiativeService(repository)
    macros = MacroService(repository, handle_roll_command)
    scenes = SceneService(repository, client=discord_client)
    reminders = ReminderCommandService(repository, manager, persistence)
    ammo = AmmoService(repository)
    user_options = UserOptions(repository)
    maintenance_status = (
        "\n**Bzzt. Hoi!** Encryption is go! `!skipstatus` to hide this message! "
        "See `!help troubleshoot` if you suspect a bug!"
    )
    options = UserOptionCommands(user_options, maintenance_status)

    async def add_maintenance_status(msg: Any, output: str) -> str:
        skipped = await user_options.get(msg.author.id, "skipStatusMsg")
        return output if skipped == maintenance_status else output + " " + maintenance_status

    help_service = HelpService(add_maintenance_status)
    dispatcher = CommandDispatcher(
        initiative=initiative, macros=macros, scenes=scenes,
        reminders=reminders, ammo=ammo, user_options=options, help_service=help_service,
    )
    accepting_commands = False

    @discord_client.event
    async def on_message(msg: Any) -> None:
        if accepting_commands and not msg.author.bot:
            await dispatcher.on_message(msg)

    @discord_client.event
    async def on_reaction_add(reaction: Any, user: Any) -> None:
        if accepting_commands:
            await dispatcher.on_reaction_add(reaction, user)

    async def initialize() -> None:
        nonlocal reminder_root
        user_data = await repository.ensure_folder("UserData", encrypted=False)
        reminder_root = str(await repository.ensure_folder("reminders", str(user_data), encrypted=False))
        await persistence.restore()

    connection = await start_bot(
        client=discord_client,
        token=settings.token,
        connect_database=store.connect,
        initialize=initialize,
        close_database=store.close,
        stop_reminders=manager.stop,
    )
    try:
        manager.start()
        accepting_commands = True
        await discord_client.change_presence(activity=__import__("discord").Game("!help"))
        await connection
    finally:
        accepting_commands = False
        manager.stop()
        await discord_client.close()
        await store.close()
