"""👎 反馈动作：触发 Lark 告警 + 标记会话 needs_review。"""

from httpx import ASGITransport, AsyncClient

_H = {"X-BU-ID": "BU00243780"}


async def _new_conv(client: AsyncClient) -> int:
    init = await client.post("/api/v1/conversations", json={}, headers=_H)
    return init.json()["conversation_id"]


async def test_down_triggers_lark_and_marks_review(seeded_db, monkeypatch):
    from ai_engine.api import feedback as fb_api
    from ai_engine import main as main_mod
    from ai_engine.persistence import db

    sent: list[dict] = []

    async def fake_lark(payload):
        sent.append(payload)

    monkeypatch.setattr(fb_api, "_notify_lark", fake_lark)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        cid = await _new_conv(client)
        r = await client.post(
            f"/api/v1/conversations/{cid}/feedback",
            json={"message_id": 42, "rating": "down", "reason": "答非所问"},
            headers=_H,
        )
    assert r.status_code == 200

    # (a) Lark 告警被调用，payload 含会话/原因
    assert len(sent) == 1
    text = sent[0]["text"]
    assert str(cid) in text
    assert "42" in text
    assert "答非所问" in text

    # (b) needs_review 被置 1
    row = await db.fetch_one(
        "SELECT needs_review FROM conversations WHERE id=:c", {"c": cid}
    )
    assert row["needs_review"] == 1


async def test_up_does_not_trigger_lark_or_review(seeded_db, monkeypatch):
    from ai_engine.api import feedback as fb_api
    from ai_engine import main as main_mod
    from ai_engine.persistence import db

    sent: list[dict] = []

    async def fake_lark(payload):
        sent.append(payload)

    monkeypatch.setattr(fb_api, "_notify_lark", fake_lark)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        cid = await _new_conv(client)
        r = await client.post(
            f"/api/v1/conversations/{cid}/feedback",
            json={"message_id": 7, "rating": "up"},
            headers=_H,
        )
    assert r.status_code == 200

    assert sent == []
    row = await db.fetch_one(
        "SELECT needs_review FROM conversations WHERE id=:c", {"c": cid}
    )
    assert row["needs_review"] == 0


async def test_down_lark_failure_does_not_block_persist(seeded_db, monkeypatch):
    """Lark 发送抛错时，反馈仍落库、needs_review 仍置 1（主流程不阻断）。"""
    from ai_engine.api import feedback as fb_api
    from ai_engine import main as main_mod
    from ai_engine.persistence import db

    async def boom(payload):
        raise RuntimeError("lark down")

    monkeypatch.setattr(fb_api, "_notify_lark", boom)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        cid = await _new_conv(client)
        r = await client.post(
            f"/api/v1/conversations/{cid}/feedback",
            json={"message_id": 9, "rating": "down"},
            headers=_H,
        )
    assert r.status_code == 200

    rows = await db.fetch_all(
        "SELECT rating FROM message_feedback WHERE conversation_id=:c", {"c": cid}
    )
    assert rows and rows[0]["rating"] == "down"
    row = await db.fetch_one(
        "SELECT needs_review FROM conversations WHERE id=:c", {"c": cid}
    )
    assert row["needs_review"] == 1
