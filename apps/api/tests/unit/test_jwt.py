import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth.jwt import verify_token
from app.config import Settings
from app.errors import Problem


def _settings() -> Settings:
    return Settings(supabase_url="http://127.0.0.1:54321", supabase_jwt_secret="x" * 40, app_env="test")


def _claims(settings: Settings, **over: object) -> dict[str, object]:
    now = int(time.time())
    base: dict[str, object] = {
        "sub": "11111111-1111-4111-8111-111111111111",
        "email": "a@b.c",
        "role": "authenticated",
        "aud": "authenticated",
        "iss": settings.auth_issuer,
        "iat": now,
        "exp": now + 60,
        "aal": "aal2",
    }
    base.update(over)
    return base


def test_hs256_roundtrip() -> None:
    s = _settings()
    token = jwt.encode(_claims(s), s.supabase_jwt_secret, algorithm="HS256")
    ctx = verify_token(token, s)
    assert ctx.user_id == "11111111-1111-4111-8111-111111111111"
    assert ctx.aal == "aal2"
    assert ctx.email == "a@b.c"


def test_hs256_wrong_secret_rejected() -> None:
    s = _settings()
    token = jwt.encode(_claims(s), "y" * 40, algorithm="HS256")
    with pytest.raises(Problem) as exc:
        verify_token(token, s)
    assert exc.value.status == 401


def test_expired_token_has_its_own_problem_type() -> None:
    s = _settings()
    token = jwt.encode(_claims(s, exp=int(time.time()) - 10), s.supabase_jwt_secret, algorithm="HS256")
    with pytest.raises(Problem) as exc:
        verify_token(token, s)
    assert exc.value.type == "token_expired"


def test_wrong_issuer_rejected() -> None:
    s = _settings()
    token = jwt.encode(_claims(s, iss="https://evil.example/auth/v1"), s.supabase_jwt_secret, algorithm="HS256")
    with pytest.raises(Problem):
        verify_token(token, s)


def test_es256_verified_against_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings()
    key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(_claims(s), key, algorithm="ES256", headers={"kid": "k1"})

    class FakeKey:
        def __init__(self) -> None:
            self.key = key.public_key()

    class FakeJwks:
        def get_signing_key_from_jwt(self, _token: str) -> FakeKey:
            return FakeKey()

    monkeypatch.setattr("app.auth.jwt._jwks_client", lambda _url: FakeJwks())
    assert verify_token(token, s).user_id == "11111111-1111-4111-8111-111111111111"


def test_unsupported_alg_rejected() -> None:
    s = _settings()
    token = jwt.encode(_claims(s), s.supabase_jwt_secret, algorithm="HS384")
    with pytest.raises(Problem):
        verify_token(token, s)
