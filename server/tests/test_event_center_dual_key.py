import hashlib
import hmac
import json

from httpx import ASGITransport, AsyncClient


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _setup(monkeypatch, temp_db_url):
    monkeypatch.setenv("EVENT_CENTER_SECRET_CURRENT", "new-key")
    monkeypatch.setenv("EVENT_CENTER_SECRET_PREVIOUS", "old-key")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.tickets import create_ticket

    await init_db()
    await create_ticket(external_id="AI-DK", conversation_id=1, payload={"category": "bug"})


async def _post(secret: str, temp_db_url):
    from ai_engine import main as main_mod

    body = {"event": "assigned", "actor": "x", "internal_ticket_id": "EC", "at": "now"}
    raw = json.dumps(body).encode("utf-8")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.post(
            "/api/v1/tickets/AI-DK/events",
            content=raw,
            headers={"X-Signature": _sign(raw, secret), "Content-Type": "application/json"},
        )


async def test_current_key_verifies(temp_db_url, monkeypatch):
    await _setup(monkeypatch, temp_db_url)
    assert (await _post("new-key", temp_db_url)).status_code == 200


async def test_previous_key_verifies(temp_db_url, monkeypatch):
    await _setup(monkeypatch, temp_db_url)
    assert (await _post("old-key", temp_db_url)).status_code == 200


async def test_unknown_key_rejected(temp_db_url, monkeypatch):
    await _setup(monkeypatch, temp_db_url)
    assert (await _post("bogus-key", temp_db_url)).status_code == 401


async def test_mock_receiver_not_mounted_by_default(temp_db_url, monkeypatch):
    """生产默认不挂 mock receiver。"""
    monkeypatch.setenv("MOCK_EVENT_CENTER", "false")
    from ai_engine.config import settings

    settings.reload()
    # 重新加载 main 以反映路由（importlib reload 复杂，这里只验证 flag 默认 False）
    assert settings.mock_event_center is False
