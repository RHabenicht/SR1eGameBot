import json
import tempfile
import unittest
from pathlib import Path

from sr1egamebot.config import ConfigurationError, load_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "TOKEN": " test-token ",
            "MONGODB_URI": "mongodb://localhost/sr1egamebot",
            "CRYPTO_KEY_HEX": "ab" * 32,
            "CRYPTO_IV_HEX": "cd" * 16,
        }

    def test_loads_environment_configuration(self):
        config = load_config(self.env)
        self.assertEqual(config.token, "test-token")
        self.assertEqual(config.crypto_key, bytes.fromhex("ab" * 32))
        self.assertEqual(config.crypto_vector, bytes.fromhex("cd" * 16))

    def test_local_token_file_is_supported_when_env_token_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            auth = Path(directory) / "discordauth.json"
            auth.write_text(json.dumps({"token": "local-token"}), encoding="utf-8")
            env = {key: value for key, value in self.env.items() if key != "TOKEN"}
            self.assertEqual(load_config(env, auth).token, "local-token")

    def test_rejects_bad_hex_without_truncating(self):
        env = dict(self.env, CRYPTO_KEY_HEX="ab" * 32 + "zz")
        with self.assertRaisesRegex(ConfigurationError, "64 hexadecimal"):
            load_config(env)

    def test_requires_existing_encryption_material(self):
        env = dict(self.env)
        del env["CRYPTO_IV_HEX"]
        with self.assertRaisesRegex(ConfigurationError, "existing databases"):
            load_config(env)

    def test_rejects_json_token_text(self):
        env = dict(self.env, TOKEN='{"token":"x"}')
        with self.assertRaisesRegex(ConfigurationError, "raw Discord bot token"):
            load_config(env)
