import base64
import os
from collections.abc import Iterator

import pytest

from app import crypto
from app.config import get_settings


@pytest.fixture(autouse=True)
def _keys(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode())
    monkeypatch.setenv("APP_ENCRYPTION_KEY_PREVIOUS", "")
    get_settings.cache_clear()
    crypto._keys.cache_clear()
    yield
    get_settings.cache_clear()
    crypto._keys.cache_clear()


def test_roundtrip_and_aad_binding() -> None:
    blob = crypto.encrypt("sk-ant-secret", "ai_credentials:ws:anthropic")
    assert crypto.decrypt(blob, "ai_credentials:ws:anthropic") == "sk-ant-secret"
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt(blob, "ai_credentials:other:anthropic")
    assert blob != crypto.encrypt("sk-ant-secret", "ai_credentials:ws:anthropic")  # fresh nonce each time


def test_rotation_window(monkeypatch: pytest.MonkeyPatch) -> None:
    old_key = get_settings().app_encryption_key
    blob = crypto.encrypt("value", "aad")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode())
    monkeypatch.setenv("APP_ENCRYPTION_KEY_PREVIOUS", old_key)
    get_settings.cache_clear()
    crypto._keys.cache_clear()
    assert crypto.decrypt(blob, "aad") == "value"
    monkeypatch.setenv("APP_ENCRYPTION_KEY_PREVIOUS", "")
    get_settings.cache_clear()
    crypto._keys.cache_clear()
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt(blob, "aad")
