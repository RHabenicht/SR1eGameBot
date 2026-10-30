"""Operations over the legacy folders/strings MongoDB schema."""

from __future__ import annotations

from typing import Any

from .crypto_compat import AESCipher
from .storage import MongoStore, object_id, folder_document, string_document


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
