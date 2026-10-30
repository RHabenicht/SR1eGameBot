"""AES compatibility with the maintained Node.js application's stored values."""

from __future__ import annotations

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class AESCipher:
    """AES-256-CBC with UTF-8 input, lowercase hex output, and PKCS#7 padding."""

    def __init__(self, key: bytes, vector: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES-256 requires a 32-byte key.")
        if len(vector) != 16:
            raise ValueError("AES-CBC requires a 16-byte initialization vector.")
        self._key = bytes(key)
        self._vector = bytes(vector)

    def encrypt(self, plaintext: str) -> str:
        if not isinstance(plaintext, str):
            raise TypeError("plaintext must be a string")
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
        encryptor = Cipher(algorithms.AES(self._key), modes.CBC(self._vector)).encryptor()
        return (encryptor.update(padded) + encryptor.finalize()).hex()

    def decrypt(self, ciphertext_hex: str) -> str:
        if not isinstance(ciphertext_hex, str) or len(ciphertext_hex) % 2:
            raise ValueError("ciphertext must be an even-length hexadecimal string")
        try:
            ciphertext = bytes.fromhex(ciphertext_hex)
        except ValueError:
            raise ValueError("ciphertext must be hexadecimal") from None
        if not ciphertext or len(ciphertext) % 16:
            raise ValueError("ciphertext must contain complete AES blocks")
        decryptor = Cipher(algorithms.AES(self._key), modes.CBC(self._vector)).decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")
