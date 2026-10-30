"""Configuration loading and validation for the Python bot."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Raised for missing or invalid bot configuration."""


@dataclass(frozen=True, slots=True)
class BotConfig:
    token: str
    db_url: str
    crypto_key: bytes
    crypto_vector: bytes


def _read_hex(env: Mapping[str, str], name: str, byte_length: int) -> bytes:
    value = env.get(name)
    if value is None:
        return b""
    if len(value) != byte_length * 2 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ConfigurationError(f"{name} must contain {byte_length * 2} hexadecimal characters.")
    return bytes.fromhex(value)


def _load_token(env: Mapping[str, str], auth_file: Path) -> str:
    if "TOKEN" in env:
        token = env["TOKEN"]
    else:
        try:
            with auth_file.open(encoding="utf-8") as source:
                token = json.load(source)["token"]
        except (OSError, ValueError, KeyError, TypeError):
            raise ConfigurationError(
                "Set TOKEN to the raw Discord bot token, or create discordauth.json with a token property."
            ) from None
    if not isinstance(token, str) or not token.strip() or any(c.isspace() for c in token.strip()) or token.strip().startswith(("{", "[")):
        raise ConfigurationError("TOKEN must contain the raw Discord bot token, not JSON.")
    return token.strip()


def load_config(
    env: Mapping[str, str] | None = None,
    auth_file: Path | str = "discordauth.json",
) -> BotConfig:
    """Load environment configuration and validate it before opening connections."""
    values = os.environ if env is None else env
    db_url = values.get("MONGODB_URI", "")
    if not isinstance(db_url, str) or not db_url.startswith(("mongodb://", "mongodb+srv://")):
        raise ConfigurationError("Set MONGODB_URI to a MongoDB connection string.")
    try:
        parsed = urlsplit(db_url)
        if not parsed.netloc:
            raise ValueError
    except ValueError:
        raise ConfigurationError("Set MONGODB_URI to a MongoDB connection string.") from None

    key = _read_hex(values, "CRYPTO_KEY_HEX", 32)
    vector = _read_hex(values, "CRYPTO_IV_HEX", 16)
    if len(key) != 32 or len(vector) != 16:
        raise ConfigurationError(
            "Set CRYPTO_KEY_HEX (32 bytes) and CRYPTO_IV_HEX (16 bytes); existing databases require their original encryption values."
        )
    return BotConfig(
        token=_load_token(values, Path(auth_file)),
        db_url=db_url,
        crypto_key=key,
        crypto_vector=vector,
    )
