from unittest.mock import AsyncMock


async def test_create_ticket_posts_to_event_center(seeded_db, monkeypatch):
    from ai_engine.agent.tools import create_ticket
    from ai_engine.persistence.tickets import get_ticket

    posted = []

    async def fake_post(url, json, headers):
        posted.append({"url": url, "json": json, "headers": headers})

        class R:
            status_code = 200

        return R()

    monkeypatch.setattr(create_ticket, "_post", fake_post)
    monkeypatch.setattr(create_ticket, "_notify_lark", AsyncMock())

    out = await create_ticket.run(
        bu_id="BU00243780",
        conversation_id=1,
        category="bug",
        summary="card_bind 偶发 500",
        severity="p1",
        evidence={"code_refs": [{"repo": "openapi_backend", "path": "handlers/card_bind.py"}]},
    )

    assert out["external_ticket_id"].startswith("AI-")
    assert posted and posted[0]["json"]["category"] == "bug"
    assert posted[0]["headers"].get("X-Signature")
    t = await get_ticket(out["external_ticket_id"])
    assert t["payload_json"]


async def test_create_ticket_falls_back_to_lark_when_center_down(seeded_db, monkeypatch):
    from ai_engine.agent.tools import create_ticket

    async def fake_post_failed(url, json, headers):
        raise RuntimeError("network down")

    lark_calls = []

    async def fake_lark(payload):
        lark_calls.append(payload)

    monkeypatch.setattr(create_ticket, "_post", fake_post_failed)
    monkeypatch.setattr(create_ticket, "_notify_lark", fake_lark)

    out = await create_ticket.run(
        bu_id="BU00243780",
        conversation_id=1,
        category="bug",
        summary="x bug summary",
        severity="p2",
        evidence={},
    )
    assert out["external_ticket_id"]
    assert lark_calls
