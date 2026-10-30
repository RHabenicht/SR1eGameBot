"""MongoDB access and legacy document-shape helpers."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import AsyncMongoClient


DATABASE_NAME = "sr1egamebot"
COLLECTION_NAMES = frozenset({"folders", "strings"})


def object_id(value: str | ObjectId) -> ObjectId:
    """Convert Mongo document IDs only; Discord snowflakes remain strings."""
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(value)
    except (InvalidId, TypeError, ValueError):
        raise ValueError("database ID must be a valid MongoDB ObjectId") from None


def discord_id(value: str | int) -> str:
    """Normalize Discord snowflakes to the string form used by existing records."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError("Discord ID must be a string or integer")
    return str(value)


def folder_document(name: str, cipher: Any, parent_id: str | ObjectId | None = None,
                    encrypted: bool = True) -> dict[str, Any]:
    document: dict[str, Any] = {
        "name": cipher.encrypt(name) if encrypted else name,
        "encrypted": encrypted,
    }
    if parent_id is not None:
        document["parent"] = object_id(parent_id)
    return document


def string_document(name: str, content: str, parent_id: str | ObjectId,
                    cipher: Any) -> dict[str, Any]:
    return {
        "name": name,
        "parent": object_id(parent_id),
        "content": cipher.encrypt(content),
        "encrypted": True,
    }


class MongoStore:
    """Async PyMongo connection to the existing database and its two collections."""

    def __init__(self, uri: str, client: Any | None = None) -> None:
        self._client = client if client is not None else AsyncMongoClient(uri)
        self._database = self._client[DATABASE_NAME]

    async def connect(self) -> None:
        await self._client.admin.command("ping")

    async def close(self) -> None:
        await self._client.close()

    def collection(self, name: str) -> Collection[Any]:
        if name not in COLLECTION_NAMES:
            raise ValueError(f"unsupported collection: {name}")
        return self._database[name]
