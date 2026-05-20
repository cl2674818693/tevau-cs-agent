import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture
def keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    return (
        priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        pub.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode(),
    )


def _setup(monkeypatch, pub):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("APP_JWT_PUBLIC_KEY", pub)
    from ai_engine.config import settings

    settings.reload()


def test_verify_valid_c_jwt(monkeypatch, keypair):
    priv, pub = keypair
    _setup(monkeypatch, pub)
    token = jwt.encode({"typ": "c", "sub": "U12345", "exp": 9999999999}, priv, algorithm="RS256")
    from ai_engine.auth.c_jwt import verify_app_jwt

    claims = verify_app_jwt(token)
    assert claims["typ"] == "c"
    assert claims["sub"] == "U12345"


def test_reject_wrong_typ(monkeypatch, keypair):
    priv, pub = keypair
    _setup(monkeypatch, pub)
    token = jwt.encode({"typ": "b", "sub": "BU1", "exp": 9999999999}, priv, algorithm="RS256")
    from ai_engine.auth.c_jwt import verify_app_jwt

    with pytest.raises(ValueError):
        verify_app_jwt(token)


def test_reject_expired(monkeypatch, keypair):
    priv, pub = keypair
    _setup(monkeypatch, pub)
    token = jwt.encode({"typ": "c", "sub": "U1", "exp": 1}, priv, algorithm="RS256")
    from ai_engine.auth.c_jwt import verify_app_jwt

    with pytest.raises(ValueError):
        verify_app_jwt(token)


async def test_resolve_identity_c_end(monkeypatch, keypair):
    """resolve_identity：带 C 端 Bearer JWT → ('c', user_id)。"""
    priv, pub = keypair
    _setup(monkeypatch, pub)
    token = jwt.encode({"typ": "c", "sub": "U777", "exp": 9999999999}, priv, algorithm="RS256")
    from starlette.requests import Request

    from ai_engine.auth.bu_session import resolve_identity

    scope = {
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    }
    ut, sid = await resolve_identity(Request(scope))
    assert ut == "c" and sid == "U777"
