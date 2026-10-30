"""Operations over the legacy folders/strings MongoDB schema."""

from __future__ import annotations

from typing import Any

from .crypto_compat import AESCipher
from .storage import MongoStore, discord_id, object_id, folder_document, string_document


class LegacyRepository:
    """Read and write existing bot records without changing their schema."""

    def __init__(self, store: MongoStore, cipher: AESCipher) -> None:
        self._store = store
        self._cipher = cipher

    async def find_folder(self, name: str, parent_id: str | None = None,
                          encrypted: bool = True) -> dict[str, Any] | None:
        query: dict[str, Any] = {
            "name": self._cipher.encrypt(name) if encrypted else name,
        }
        if parent_id is not None:
            query["parent"] = object_id(parent_id)
        return await self._store.collection("folders").find_one(query)

    async def create_folder(self, name: str, parent_id: str | None = None,
                            encrypted: bool = True) -> Any:
        document = folder_document(name, self._cipher, parent_id, encrypted)
        result = await self._store.collection("folders").insert_one(document)
        return result.inserted_id

    async def ensure_folder(self, name: str, parent_id: str | None = None,
                            encrypted: bool = True) -> Any:
        found = await self.find_folder(name, parent_id, encrypted)
        if found is not None:
            return found["_id"]
        return await self.create_folder(name, parent_id, encrypted)

    async def find_string(self, name: str, parent_id: str) -> dict[str, Any] | None:
        return await self._store.collection("strings").find_one({
            "name": name,
            "parent": object_id(parent_id),
        })

    async def get_string(self, file_id: str) -> str:
        record = await self._store.collection("strings").find_one({"_id": object_id(file_id)})
        if not record or not record.get("content"):
            return ""
        content = record["content"]
        return self._cipher.decrypt(content) if record.get("encrypted") else content

    async def set_string(self, name: str, parent_id: str, content: str) -> Any:
        parent = object_id(parent_id)
        document = string_document(name, content, parent, self._cipher)
        result = await self._store.collection("strings").update_one(
            {"name": name, "parent": parent},
            {"$set": document},
            upsert=True,
        )
        return result

    async def delete_string(self, file_id: str) -> int:
        result = await self._store.collection("strings").delete_one({"_id": object_id(file_id)})
        return result.deleted_count

    async def find_user_folder(self, server_id: str | int, channel_id: str | int,
                               user_id: str | int) -> dict[str, Any] | None:
        root = await self.find_folder("UserData", encrypted=False)
        if root is None:
            return None
        server = await self.find_folder(discord_id(server_id), str(root["_id"]))
        if server is None:
            return None
        channel = await self.find_folder(discord_id(channel_id), str(server["_id"]))
        if channel is None:
            return None
        return await self.find_folder(discord_id(user_id), str(channel["_id"]))

    async def ensure_user_folder(self, server_id: str | int, channel_id: str | int,
                                 user_id: str | int) -> Any:
        root_id = await self._ensure_root_folder()
        server_id_db = await self.ensure_folder(discord_id(server_id), str(root_id))
        channel_id_db = await self.ensure_folder(discord_id(channel_id), str(server_id_db))
        return await self.ensure_folder(discord_id(user_id), str(channel_id_db))

    async def _ensure_root_folder(self) -> Any:
        existing = await self.find_folder("UserData", encrypted=False)
        if existing is not None:
            return existing["_id"]
        return await self.create_folder("UserData", encrypted=False)

    async def get_play_channel(self, server_id: str | int, channel_id: str | int,
                               user_id: str | int) -> str:
        channel = discord_id(channel_id)
        user_folder = await self.find_user_folder(server_id, channel, user_id)
        if user_folder is None:
            return channel
        record = await self.find_string("gmPlayChannel", str(user_folder["_id"]))
        if record is None:
            return channel
        saved = await self.get_string(str(record["_id"]))
        return saved or channel

    async def set_play_channel(self, server_id: str | int, channel_id: str | int,
                               user_id: str | int, play_channel_id: str | int) -> None:
        folder_id = await self.ensure_user_folder(server_id, channel_id, user_id)
        await self.set_string("gmPlayChannel", str(folder_id), discord_id(play_channel_id))
