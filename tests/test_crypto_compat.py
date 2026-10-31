import unittest

from sr1egamebot.crypto_compat import AESCipher


# Golden ciphertexts were produced by Node.js crypto.createCipheriv('aes-256-cbc')
# using the same synthetic key and IV as the maintained branch's storage tests.
VECTORS = {
    "server-a": "17373b6b70905862c5152d5e33bdb759",
    "smoketest 5! tn4": "47510b74e4b4901ac8e6ceefe04720956abdb6f0b426cbe0155572617b293a37",
    "Shadowrun 東京": "37ea5cfe5ad44e8acd7dcadc8e2c297527689d6238600353872ce3cf65ddcffc",
}


class CryptoCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.cipher = AESCipher(bytes([7]) * 32, bytes([8]) * 16)

    def test_python_output_matches_node_ciphertext_fixtures(self):
        for plaintext, expected in VECTORS.items():
            with self.subTest(plaintext=plaintext):
                self.assertEqual(self.cipher.encrypt(plaintext), expected)

    def test_decrypts_node_ciphertext_fixtures(self):
        for plaintext, ciphertext in VECTORS.items():
            with self.subTest(plaintext=plaintext):
                self.assertEqual(self.cipher.decrypt(ciphertext), plaintext)

    def test_rejects_invalid_key_vector_and_ciphertext_shapes(self):
        with self.assertRaises(ValueError):
            AESCipher(b"short", bytes(16))
        with self.assertRaises(ValueError):
            AESCipher(bytes(32), b"short")
        with self.assertRaises(ValueError):
            self.cipher.decrypt("abc")
