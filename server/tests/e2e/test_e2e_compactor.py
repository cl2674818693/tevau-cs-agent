"""E2E 剧本 #7：会话长度治理 → compactor 总结 → 新会话继承结论。

剧本梗概：
    1. 预填 20+ 轮 user 消息到旧会话（直接 DAO 落 user 行 done），
       触发 should_compact=True。
    2. 用户继续发新消息（chat 端点）→ runtime._maybe_compact() 调
       compact_conversation 总结老会话、开新 conv_id，并 yield system 事件
       ("会话过长，已为您开启新对话")。
    3. assert：
       - 老会话 archived=1，
       - 新会话表里有一条 role='system' 的摘要消息（_summarize 的输出），
       - SSE 流里能看到 warning 事件。
    4. 在新会话继续 chat → 走正常 ai 路径。

异常分支：
    - _summarize 抛错 → runtime 自身无 try/except，冒到 chat.py 顶层 try →
      回 INTERNAL_ERROR。
"""

from types import SimpleNamespace

import pytest_asyncio
from httpx import AsyncClient

from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence.schema import now_str

from .conftest import event_data, parse_sse


async def _seed_long_history(conv_id: int, turns: int = 21) -> None:
    """直接落 N 条已完成的 user 回合，触发 should_compact=True。"""
    from ai_engine.persistence import db as db_mod

    for i in range(turns):
        await db_mod.execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', :c, 'done', :now)",
            {"cid": conv_id, "c": f"老问题 {i}", "now": now_str()},
        )


@pytest_asyncio.fixture
async def long_conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    cid = int(r.json()["conversation_id"])
    await _seed_long_history(cid, turns=21)
    return cid


@pytest_asyncio.fixture
def stub_summary(monkeypatch):
    """把 _summarize 短路成确定文本，不打 Anthropic。"""
    from ai_engine.agent import conversation_compactor as cc

    async def _fake_summarize(history: str) -> str:
        return "[摘要] 用户咨询过 20+ 轮，主要诉求是查卡片状态，已建议联系客服。"

    monkeypatch.setattr(cc, "_summarize", _fake_summarize)


class TestCompactor:
    async def test_should_compact_at_20_turns(self, long_conv_id: int) -> None:
        from ai_engine.governance.conversation_limits import should_compact

        assert await should_compact(long_conv_id) is True

    async def test_full_chat_triggers_compaction_and_new_conversation(
        self, c_client: AsyncClient, long_conv_id: int, stub_summary, monkeypatch
    ) -> None:
        """chat 端点触发 _maybe_compact → 老会话归档 + 新会话建 + 流出 warning。"""

        # 让 LLM stub 在新会话上回固定文本（注意 stub_run_turn 会把所有 chat 调用的 LLM 都换掉）
        # 这里直接 patch runtime.run_turn 以观察 conversation_id 是否换了。
        from ai_engine.agent import runtime as _rt
        from ai_engine.api import chat as _chat

        seen_conv_ids: list[int] = []

        # 我们要保留真实 _maybe_compact，不能整段 stub run_turn；
        # 改 stub _ac.stream_turn 即可（让 anthropic 调用返回固定 final）。
        from ai_engine.integrations import anthropic_client as _ac

        async def _fake_stream(req):
            yield {"text_delta": "好的，我帮您看看。"}
            final = SimpleNamespace(
                content=[SimpleNamespace(type="text", text="好的，我帮您看看。")],
                stop_reason="end_turn",
                usage=SimpleNamespace(input_tokens=10, output_tokens=5),
            )
            yield {"final": final}

        monkeypatch.setattr(_ac, "stream_turn", _fake_stream)
        # 关掉前置话题分类，避免再去打 haiku
        monkeypatch.setattr(_rt.settings, "topic_classifier_enabled", False, raising=False)
        # 关掉 prompt 缓存影响，确保 build_system_blocks 能跑（依赖真实 prompt 文件已存在）

        # 监控 run_turn 入口 conv_id
        orig_run_turn = _rt.run_turn

        async def _watch_run_turn(**kw):
            seen_conv_ids.append(kw.get("conversation_id"))
            async for ev in orig_run_turn(**kw):
                yield ev

        monkeypatch.setattr(_chat.runtime, "run_turn", _watch_run_turn)

        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": long_conv_id, "message": "我还想问个新问题"},
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        # 收到 warning(会话过长，已为您开启新对话, conversation_id=NEW)
        warnings = event_data(frames, "warning")
        assert any("已为您开启新对话" in w["text"] for w in warnings)
        # 老会话已归档
        from ai_engine.persistence import db as db_mod

        row = await db_mod.fetch_one(
            "SELECT archived FROM conversations WHERE id=:id", {"id": long_conv_id}
        )
        assert int(row["archived"]) == 1
        # 新会话存在且首条 system = 摘要
        rows = await db_mod.fetch_all(
            "SELECT id FROM conversations WHERE id != :old ORDER BY id DESC",
            {"old": long_conv_id},
        )
        assert rows
        new_id = int(rows[0]["id"])
        msgs = await conv_dao.list_messages(new_id)
        # 至少应有 system 摘要 + 后续 user 入库
        assert any(m["role"] == "system" and "[摘要]" in str(m["content"]) for m in msgs)
        # run_turn 入参的 conv_id 是老会话 id（runtime 内部切到 new_id，对外接口签名仍是老）
        assert seen_conv_ids == [long_conv_id]

    async def test_short_conv_does_not_compact(self, c_client: AsyncClient) -> None:
        r = await c_client.post("/api/v1/conversations", json={})
        cid = int(r.json()["conversation_id"])
        from ai_engine.governance.conversation_limits import should_compact

        assert await should_compact(cid) is False

    async def test_summarize_failure_falls_back_to_internal_error(
        self,
        c_client: AsyncClient,
        long_conv_id: int,
        monkeypatch,
    ) -> None:
        """_summarize 抛错 → runtime.run_turn 顶层捕获 → user 端口 internal error 兜底文案。"""
        from ai_engine.agent import conversation_compactor as cc

        async def _boom(history: str) -> str:
            raise RuntimeError("anthropic down")

        monkeypatch.setattr(cc, "_summarize", _boom)
        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": long_conv_id, "message": "再来一条"},
        )
        # SSE 200 但 body 是 error 帧
        assert r.status_code == 200
        frames = await parse_sse(r)
        errors = event_data(frames, "error")
        assert any(e.get("code") == "INTERNAL_ERROR" for e in errors)
