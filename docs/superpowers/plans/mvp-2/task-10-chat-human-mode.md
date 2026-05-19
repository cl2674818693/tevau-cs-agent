# Task 10: chat 端点扩展：human_takeover 时跳过 agent + 用户消息推给客服

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `server/src/ai_engine/api/chat.py`
- Modify: `server/src/ai_engine/agent/runtime.py`（如有必要）
- Create: `server/tests/test_chat_human_mode.py`

- [ ] **Step 1: 写 `server/tests/test_chat_human_mode.py`**

```python
async def test_user_message_in_human_takeover_skips_agent(temp_db_url, monkeypatch):
    """human_takeover 模式下，用户发消息只入库 + 推客服侧，不调 LLM"""
    monkeypatch.setenv("STAFF_JWT_SECRET", "x")
    from ai_engine.config import settings
    settings.reload()

    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.conversations import create_conversation, set_mode, list_messages
    from ai_engine.persistence.staff import create_staff
    await init_db()
    await create_staff("S100", "张三", "agent", "x")

    cid = await create_conversation(user_type="b", subject_id="BU00243780")
    await set_mode(cid, "human_takeover", "S100")

    # 用户发消息
    from httpx import AsyncClient, ASGITransport
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        async with client.stream(
            "POST", "/api/v1/chat",
            json={"conversation_id": cid, "message": "我的卡为啥被锁"},
            cookies={"ai_engine_session": "BU00243780"},
        ) as resp:
            text_lines = [l async for l in resp.aiter_lines()]

    # 应有 system 事件告知用户"客服已接管"，无 tool_call / 无 LLM 文本
    assert not any('"type":"tool_call"' in l for l in text_lines)
    # 用户消息已落库
    msgs = await list_messages(cid)
    assert any(m["role"] == "user" and "锁" in m["content"] for m in msgs)
```

- [ ] **Step 2: 修 `server/src/ai_engine/api/chat.py`**

```python
# 在 gen() 内加分支：
async def gen():
    mode, _ = await conv_dao.get_mode(conv_id) if body.conversation_id else ("ai", None)
    yield {"event": "conversation",
           "data": json.dumps({"type": "conversation",
                               "conversation_id": conv_id,
                               "user_type": user_type, "mode": mode})}

    if mode in ("human_takeover", "human_pending"):
        # 不调 AI，只落库 + 推给客服
        await append_message(conv_id, role="user", content=body.message)
        from ai_engine.api.staff_conversations import _publish
        _publish(conv_id, {"type": "user_message", "content": body.message})
        yield {"event": "system",
               "data": json.dumps({"type": "system",
                                   "text": "您的消息已转给客服，请稍候。"})}
        yield {"event": "done", "data": json.dumps({"type": "done"})}
        return

    # 否则走 AI agent loop（原 MVP-1 逻辑）
    async for ev in runtime.run_turn(...):
        yield {...}
    yield {"event": "done", "data": json.dumps({"type": "done"})}
```

- [ ] **Step 3: 跑测试 + Commit**

```bash
pytest tests/test_chat_human_mode.py -v
git add server/src/ai_engine/api/chat.py server/tests/test_chat_human_mode.py
git commit -m "feat(mvp-2): chat 端点支持 human_takeover 模式（跳过 AI，消息推给客服）"
```

---
