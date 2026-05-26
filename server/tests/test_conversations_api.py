import json

from httpx import ASGITransport, AsyncClient

_BU = "BU00243780"


async def _seed_conversation_with_history(subject_id: str = _BU) -> int:
    """建一条带 user/assistant/human_agent 历史的 B 端会话，返回 conv_id。"""
    from ai_engine.persistence.conversations import (
        append_human_message,
        append_message,
        append_user_turn,
        create_conversation,
        finalize_turn,
    )

    cid = await create_conversation("b", subject_id)
    tid = await append_user_turn(cid, "我的卡为什么被锁", None)
    await finalize_turn(tid, "done")
    # assistant 入库是 json blob，历史接口需还原成纯文本
    await append_message(cid, "assistant", json.dumps([{"type": "text", "text": "因为风控规则"}]))
    await append_human_message(cid, "S1", "我已帮你解锁")
    return cid


async def test_resume_reuses_owned_conversation(seeded_db):
    cid = await _seed_conversation_with_history()
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/conversations", json={"resume": cid}, headers={"X-BU-ID": _BU}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"] == cid  # 续接的是同一条，不新建
    assert body["mode"] == "ai"
    assert body["history_url"] == f"/api/v1/conversations/{cid}/messages"


async def test_resume_unowned_creates_new(seeded_db):
    """resume 一条不属于当前身份的会话 → 不续接，新建（返回不同 id）。"""
    other = await _seed_conversation_with_history(subject_id="BU99999999")
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/conversations", json={"resume": other}, headers={"X-BU-ID": _BU}
        )
    assert resp.status_code == 200
    assert resp.json()["conversation_id"] != other


async def test_resume_archived_creates_new(seeded_db):
    """已归档会话不续接（spec §8），新建。"""
    from ai_engine.persistence.conversations import archive_conversation

    cid = await _seed_conversation_with_history()
    await archive_conversation(cid)
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/conversations", json={"resume": cid}, headers={"X-BU-ID": _BU}
        )
    assert resp.status_code == 200
    assert resp.json()["conversation_id"] != cid


async def test_history_returns_user_facing_messages(seeded_db):
    cid = await _seed_conversation_with_history()
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/conversations/{cid}/messages", headers={"X-BU-ID": _BU}
        )
    assert resp.status_code == 200
    msgs = resp.json()["messages"]
    assert msgs == [
        {"role": "user", "content": "我的卡为什么被锁", "attachments": []},
        {"role": "assistant", "content": "因为风控规则", "attachments": []},  # json blob 已还原
        {"role": "human_agent", "content": "我已帮你解锁", "attachments": []},
    ]


async def test_history_includes_attachments(seeded_db):
    """图片消息：历史回放带 attachments（对齐前端 Attachment {id, mime}）。"""
    from ai_engine.persistence.attachments import bind_attachments, create_attachment
    from ai_engine.persistence.conversations import (
        append_user_turn,
        create_conversation,
        finalize_turn,
    )

    cid = await create_conversation("b", _BU)
    aid = await create_attachment(cid, "b", _BU, "key/1.png", "image/png", 100, "sha")
    mid = await append_user_turn(cid, "看这张图", None)
    await finalize_turn(mid, "done")
    await bind_attachments(mid, cid, _BU, [aid])

    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/conversations/{cid}/messages", headers={"X-BU-ID": _BU}
        )
    assert resp.status_code == 200
    msgs = resp.json()["messages"]
    assert msgs == [
        {"role": "user", "content": "看这张图", "attachments": [{"id": aid, "mime": "image/png"}]}
    ]


async def test_history_caps_recent_messages(seeded_db):
    """超过上限只返回最近 N 条。"""
    from ai_engine.api import conversations as conv_api
    from ai_engine.persistence.conversations import append_message, create_conversation

    cid = await create_conversation("b", _BU)
    total = conv_api._HISTORY_MAX_MESSAGES + 5
    for i in range(total):
        await append_message(cid, "assistant", json.dumps([{"type": "text", "text": f"m{i}"}]))

    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/conversations/{cid}/messages", headers={"X-BU-ID": _BU}
        )
    msgs = resp.json()["messages"]
    assert len(msgs) == conv_api._HISTORY_MAX_MESSAGES
    assert msgs[-1]["content"] == f"m{total - 1}"  # 保留的是最近的
    assert msgs[0]["content"] == f"m{total - conv_api._HISTORY_MAX_MESSAGES}"


async def test_resume_restores_staff_name(seeded_db):
    """续接 human_takeover 会话 → init 返回客服署名。"""
    from ai_engine.persistence.conversations import create_conversation, set_mode
    from ai_engine.persistence.staff import create_staff

    await create_staff("S1", "客服小王", "agent", "pw")
    cid = await create_conversation("b", _BU)
    await set_mode(cid, "human_takeover", assigned_staff_id="S1")

    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/conversations", json={"resume": cid}, headers={"X-BU-ID": _BU}
        )
    body = resp.json()
    assert body["mode"] == "human_takeover"
    assert body["staff_name"] == "客服小王"


async def test_history_forbidden_for_other_identity(seeded_db):
    """属主校验：别的身份拿不到这条会话历史。"""
    cid = await _seed_conversation_with_history()
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/conversations/{cid}/messages", headers={"X-BU-ID": "BU99999999"}
        )
    assert resp.status_code == 403


async def test_conversations_init_returns_user_type_b(seeded_db):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/conversations", json={}, headers={"X-BU-ID": "BU00243780"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_type"] == "b"
    assert body["conversation_id"]
    assert body["display_name"]
    assert body["greeting"]
    assert "limits" in body


async def test_conversations_init_falls_back_to_guest(seeded_db):
    """无 cookie / 无 X-BU-ID / 无 Bearer → 降级游客会话（user_type=g），不再 401。"""
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/conversations", json={})
    assert resp.status_code == 200
    assert resp.json()["user_type"] == "g"
