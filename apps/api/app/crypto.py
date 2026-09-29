"""AES-256-GCM for credentials at rest (Section 6.7). Two-key window for rotation: encrypt with the current key,
decrypt with current then previous. Associated data binds a ciphertext to its row."""

import base64
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

NONCE_BYTES = 12


class DecryptError(ValueError):
    pass


def _decode(key_b64: str) -> bytes:
    raw = base64.b64decode(key_b64)
    if len(raw) != 32:
        raise ValueError("APP_ENCRYPTION_KEY must decode to 32 bytes")
    return raw


@lru_cache
def _keys() -> tuple[bytes, ...]:
    s = get_settings()
    if not s.app_encryption_key:
        raise RuntimeError("APP_ENCRYPTION_KEY is not set; run scripts/env.sh or set it in the environment")
    keys = [_decode(s.app_encryption_key)]
    if s.app_encryption_key_previous:
        keys.append(_decode(s.app_encryption_key_previous))
    return tuple(keys)


def encrypt(plaintext: str, aad: str) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(_keys()[0]).encrypt(nonce, plaintext.encode(), aad.encode())


def decrypt(blob: bytes, aad: str) -> str:
    nonce, body = bytes(blob[:NONCE_BYTES]), bytes(blob[NONCE_BYTES:])
    for key in _keys():
        try:
            return AESGCM(key).decrypt(nonce, body, aad.encode()).decode()
        except InvalidTag:
            continue
    raise DecryptError("ciphertext does not match any configured key")
