# SR1eGameBot Python port

This is the separate Python development line for the existing SR1eGameBot.
The Node.js bot remains the maintained application until a separately reviewed
cutover. Do not point this version at production credentials or the production
database while it is under development.

## Current status

This is an incomplete development port. Python services now cover configuration
and startup sequencing, d6 rolls and command parsing, AES-256-CBC compatibility,
the existing MongoDB folder/string schema, macros, scenes, reminders, initiative
data and ammunition. The Discord event loop and command wiring are not complete,
so this is not yet a runnable replacement for the Node.js worker.

Run the isolated unit suite with `uv run --locked python -m unittest discover -s tests -v`.
The tests use synthetic credentials and an in-memory MongoDB substitute. They do
not prove compatibility against a live database or Discord application.

The port must preserve the current command interface, saved records, encryption
compatibility, reminder restoration and disabled legacy admin commands. Live
checks require a separate Discord application and isolated test database.

## Configuration

Set `TOKEN`, `MONGODB_URI`, `CRYPTO_KEY_HEX`, and `CRYPTO_IV_HEX` in the runtime
environment. A local `discordauth.json` with a `token` property is supported
when `TOKEN` is absent. Use the original encryption key and IV only with a
compatible copy of the existing database. Keep secrets out of source control.
