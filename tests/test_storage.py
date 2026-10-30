import unittest
from unittest.mock import AsyncMock

from bson import ObjectId
from types import SimpleNamespace

from sr1egamebot.crypto_compat import AESCipher
from sr1egamebot.storage import MongoStore, discord_id, folder_document, object_id, string_document
from sr1egamebot.repository import LegacyRepository


class StorageCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.cipher = AESCipher(bytes([7]) * 32, bytes([8]) * 16)
        self.parent = ObjectId("507f1f77bcf86cd799439011")

    def test_encrypted_folder_matches_existing_shape_and_objectid_parent(self):
        folder = folder_document("server-a", self.cipher, str(self.parent))
        self.assertEqual(folder, {
            "name": "17373b6b70905862c5152d5e33bdb759",
            "encrypted": True,
            "parent": self.parent,
        })

    def test_unencrypted_root_folder_keeps_plain_name(self):
        self.assertEqual(folder_document("UserData", self.cipher, encrypted=False),
                         {"name": "UserData", "encrypted": False})

    def test_string_document_keeps_name_plain_and_encrypts_content(self):
        record = string_document("savedRolls", "smoketest 5! tn4", self.parent, self.cipher)
        self.assertEqual(record, {
            "name": "savedRolls",
            "parent": self.parent,
            "content": "47510b74e4b4901ac8e6ceefe04720956abdb6f0b426cbe0155572617b293a37",
            "encrypted": True,
        })

    def test_discord_ids_remain_strings_while_database_ids_are_objectids(self):
        self.assertEqual(discord_id(123456789012345678), "123456789012345678")
        self.assertEqual(discord_id("123456789012345678"), "123456789012345678")
        self.assertIsInstance(object_id(str(self.parent)), ObjectId)
        with self.assertRaises(ValueError):
            object_id("not-a-database-id")


class MongoStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_legacy_database_and_validates_collection_names(self):
        client = AsyncMock()
        client.__getitem__.return_value = {"folders": "folders-table", "strings": "strings-table"}
        client.admin = AsyncMock()
        store = MongoStore("mongodb://unused", client=client)
        await store.connect()
        client.admin.command.assert_awaited_once_with("ping")
        self.assertEqual(store.collection("folders"), "folders-table")
        with self.assertRaises(ValueError):
            store.collection("users")
        await store.close()
        client.close.assert_awaited_once()


class MemoryCollection:
    def __init__(self):
        self.documents = []

    async def find_one(self, query):
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document.copy()
        return None

    async def insert_one(self, document):
        stored = {"_id": ObjectId(), **document}
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def update_one(self, query, update, upsert=False):
        document = await self.find_one(query)
        if document is None:
            if not upsert:
                return SimpleNamespace(matched_count=0, upserted_id=None)
            document = {"_id": ObjectId(), **query}
            self.documents.append(document)
        for key, value in update.get("$set", {}).items():
            document[key] = value
        return SimpleNamespace(matched_count=1, upserted_id=None)

    async def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if all(document.get(key) == value for key, value in query.items()):
                del self.documents[index]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class MemoryStore:
    def __init__(self):
        self.tables = {"folders": MemoryCollection(), "strings": MemoryCollection()}

    def collection(self, name):
        return self.tables[name]


class LegacyRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_saved_data_round_trips_and_survives_repository_restart(self):
        store = MemoryStore()
        cipher = AESCipher(bytes([7]) * 32, bytes([8]) * 16)
        first_process = LegacyRepository(store, cipher)
        root_id = await first_process.create_folder("UserData", encrypted=False)
        server_id = await first_process.ensure_folder("server-a", str(root_id))
        channel_id = await first_process.ensure_folder("channel-a", str(server_id))
        user_id = await first_process.ensure_folder("123456789012345678", str(channel_id))
        await first_process.set_string("savedRolls", str(user_id), "smoketest 5! tn4")

        second_process = LegacyRepository(store, cipher)
        user = await second_process.find_folder("123456789012345678", str(channel_id))
        saved_rolls = await second_process.find_string("savedRolls", str(user["_id"]))
        self.assertEqual(await second_process.get_string(str(saved_rolls["_id"])),
                         "smoketest 5! tn4")
        self.assertTrue(saved_rolls["encrypted"])
        self.assertEqual(saved_rolls["name"], "savedRolls")
        self.assertEqual(await second_process.ensure_folder("server-a", str(root_id)), server_id)

    async def test_string_delete_uses_mongodb_objectid(self):
        store = MemoryStore()
        repository = LegacyRepository(store, AESCipher(bytes([7]) * 32, bytes([8]) * 16))
        parent_id = await repository.create_folder("UserData", encrypted=False)
        await repository.set_string("sample", str(parent_id), "value")
        record = await repository.find_string("sample", str(parent_id))
        self.assertEqual(await repository.delete_string(str(record["_id"])), 1)
        self.assertEqual(await repository.find_string("sample", str(parent_id)), None)
