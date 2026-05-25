import json

from httpx import ASGITransport, AsyncClient

_H = {"X-BU-ID": "BU00243780"}


async def test_chat_replays_on_duplicate_client_message_id(seeded_db, monkeypatch):
    """同一 client_message_id 第二次请求：重放已存回复，不再调 run_turn。"""
    from ai_engine import main as main_mod
    from ai_engine.agent import runtime

    calls = {"n": 0}

    async def fake_run_turn(**kwargs):
        calls["n"] += 1
        from ai_engine.persistence.conversations import (
            append_message,
            append_user_turn,
            finalize_turn,
        )

        tid = await append_user_turn(
            kwargs["conversation_id"], kwargs["user_message"], kwargs.get("client_message_id")
        )
        await append_message(
            kwargs["conversation_id"],
            "assistant",
            json.dumps([{"type": "text", "text": "原始答复"}], ensure_ascii=False),
        )
        await finalize_turn(tid, "done")
        yield {"type": "text", "text": "原始答复"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        init = await client.post("/api/v1/conversations", json={}, headers=_H)
        cid = init.json()["conversation_id"]
        url = f"/api/v1/chat?conversation_id={cid}&message=hi&client_message_id=cm-dup"
        async with client.stream("GET", url, headers=_H) as r1:
            _ = [line async for line in r1.aiter_lines()]
        async with client.stream("GET", url, headers=_H) as r2:
            lines2 = [line async for line in r2.aiter_lines()]

    assert calls["n"] == 1  # 第二次未再调 run_turn
    assert any("replayed" in line for line in lines2)
    assert any("原始答复" in line for line in lines2)


async def test_chat_maps_runtime_error_event(seeded_db, monkeypatch):
    """runtime fail-soft 的 error 事件应被映射成 SSE error 帧。"""
    from ai_engine import main as main_mod
    from ai_engine.agent import runtime

    async def fake_run_turn(**kwargs):
        yield {"type": "error", "code": "INTERNAL_ERROR", "text": "兜底文案"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        init = await client.post("/api/v1/conversations", json={}, headers=_H)
        cid = init.json()["conversation_id"]
        async with client.stream(
            "GET", f"/api/v1/chat?conversation_id={cid}&message=hi", headers=_H
        ) as r:
            lines = [line async for line in r.aiter_lines()]

    assert any("INTERNAL_ERROR" in line for line in lines)
    assert any("兜底文案" in line for line in lines)
