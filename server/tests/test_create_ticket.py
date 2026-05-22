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
        subject_id="BU00243780",
        user_type="b",
        conversation_id=1,
        category="bug",
        summary="card_bind 偶发 500",
        severity="p1",
        evidence={"code_refs": [{"repo": "openapi_backend", "path": "handlers/card_bind.py"}]},
    )

    assert out["external_ticket_id"].startswith("AI-")
    assert posted and posted[0]["json"]["category"] == "bug"
    assert posted[0]["json"]["user_type"] == "b"
    assert posted[0]["json"]["bu_id"] == "BU00243780"
    assert "user_id" not in posted[0]["json"]
    assert posted[0]["headers"].get("X-Signature")
    t = await get_ticket(out["external_ticket_id"])
    assert t["payload_json"]


async def test_create_ticket_c_side_fills_user_id(seeded_db, monkeypatch):
    from ai_engine.agent.tools import create_ticket

    posted = []

    async def fake_post(url, json, headers):
        posted.append({"url": url, "json": json, "headers": headers})

        class R:
            status_code = 200

        return R()

    monkeypatch.setattr(create_ticket, "_post", fake_post)
    monkeypatch.setattr(create_ticket, "_notify_lark", AsyncMock())

    out = await create_ticket.run(
        subject_id="U10086",
        user_type="c",
        conversation_id=1,
        category="事务",
        summary="卡片被锁求解锁",
        severity="p2",
        evidence={},
    )

    assert out["external_ticket_id"].startswith("AI-")
    assert posted[0]["json"]["user_type"] == "c"
    assert posted[0]["json"]["user_id"] == "U10086"
    assert "bu_id" not in posted[0]["json"]


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
        subject_id="BU00243780",
        user_type="b",
        conversation_id=1,
        category="bug",
        summary="x bug summary",
        severity="p2",
        evidence={},
    )
    assert out["external_ticket_id"]
    assert lark_calls


async def test_create_ticket_dedupes_open_ticket_within_24h(seeded_db, monkeypatch):
    """spec §11：同 subject 24h 内已有未关闭工单 → 追加证据，不新建。"""
    from ai_engine.agent.tools import create_ticket
    from ai_engine.persistence.tickets import get_ticket

    posts = []

    async def fake_post(url, json, headers):
        posts.append(json)

        class R:
            status_code = 200

        return R()

    monkeypatch.setattr(create_ticket, "_post", fake_post)
    monkeypatch.setattr(create_ticket, "_notify_lark", AsyncMock())

    first = await create_ticket.run(
        subject_id="BU99999",
        user_type="b",
        conversation_id=1,
        category="bug",
        summary="第一单",
        severity="p2",
        evidence={},
    )
    second = await create_ticket.run(
        subject_id="BU99999",
        user_type="b",
        conversation_id=1,
        category="bug",
        summary="补充证据",
        severity="p2",
        evidence={"log": "extra"},
    )

    assert second["external_ticket_id"] == first["external_ticket_id"]
    assert second.get("appended_to_existing") is True
    assert len(posts) == 1  # 第二次不再推事项中心
    t = await get_ticket(first["external_ticket_id"])
    assert any(e["event"] == "evidence_added" for e in t["events"])
