# SR1eGameBot Python port

This is the separate Python development line for the existing SR1eGameBot.
The Node.js bot remains the maintained application until a separately reviewed
cutover. Do not point this version at production credentials or the production
database while it is under development.

## Current status

The first porting stage contains configuration validation, safe startup
sequencing, and deterministic-testable Shadowrun d6 rolling primitives. It is
not yet a complete Discord bot and does not yet connect to Discord or MongoDB.

The port must preserve the current command interface, MongoDB records,
AES-256-CBC compatibility, reminder restoration, and disabled legacy admin
commands. Live checks require a separate Discord application and isolated test
database.

## Configuration

Set `TOKEN`, `MONGODB_URI`, `CRYPTO_KEY_HEX`, and `CRYPTO_IV_HEX` in the runtime
environment. A local `discordauth.json` with a `token` property is supported
when `TOKEN` is absent. Use the original encryption key and IV only with a
compatible copy of the existing database. Keep secrets out of source control.
