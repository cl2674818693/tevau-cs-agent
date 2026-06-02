"""E2E 剧本 #8：topic_classifier 三态全链路。

剧本梗概：
    1. 开启 topic_classifier；stub classify 返回 "no"/"yes"/"uncertain"。
    2. "no" → SSE 一次性流出固定 refusal 文案，不进 agent_loop，不调主 LLM；
       message_feedback 不写；user 行 status=done + topic_verdict='no'。
    3. "yes" → 正常进 agent_loop（用 fake stream_turn 返回固定 text）。
    4. "uncertain" → 进 agent_loop，但 system_blocks 多注入 UNCERTAIN_HINT 块。
    5. classify 异常 → fail-open 到 "uncertain"。

异常分支：
    - 纯空消息（empty whitespace）→ 跳过分类（runtime 内 if user_message.strip()）。
"""

from types import SimpleNamespace

import pytest_asyncio
from httpx import AsyncClient

from ai_engine.persistence import conversations as conv_dao

from .conftest import event_data, parse_sse


@pytest_asyncio.fixture
def enable_classifier(monkeypatch):
    """打开 topic_classifier 开关。"""
    from ai_engine.config import settings

    monkeypatch.setattr(settings, "topic_classifier_enabled", True, raising=False)
    yield


@pytest_asyncio.fixture
def mock_classify(monkeypatch):
    """工厂：注入 classify 的伪返回值。"""

    def _factory(verdict: str) -> None:
        from ai_engine.agent import topic_classifier as tc

        async def _fake(msg: str):
            if verdict == "boom":
                raise RuntimeError("classifier down")
            return verdict

        monkeypatch.setattr(tc, "classify", _fake)

    return _factory


@pytest_asyncio.fixture
def fake_main_llm(monkeypatch):
    """让主 LLM stream_turn 返回固定文本，专用 yes/uncertain 路径。"""
    from ai_engine.integrations import anthropic_client as _ac

    async def _fake_stream(req):
        yield {"text_delta": "ok"}
        yield {
            "final": SimpleNamespace(
                content=[SimpleNamespace(type="text", text="ok")],
                stop_reason="end_turn",
                usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            )
        }

    monkeypatch.setattr(_ac, "stream_turn", _fake_stream)


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    return int(r.json()["conversation_id"])


class TestClassifierVerdicts:
    async def test_no_returns_refusal_without_calling_main_llm(
        self,
        c_client: AsyncClient,
        conv_id: int,
        enable_classifier,
        mock_classify,
        monkeypatch,
    ) -> None:
        """no → 直接 refusal；主 LLM 不被调。"""
        mock_classify("no")

        # 主 LLM 一旦被调就失败
        async def _boom_stream(req):
            raise AssertionError("main LLM should not be called when verdict=no")
            yield  # pragma: no cover

        from ai_engine.integrations import anthropic_client as _ac

        monkeypatch.setattr(_ac, "stream_turn", _boom_stream)

        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "今天天气怎么样？"},
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        deltas = event_data(frames, "content_block_delta")
        all_text = "".join(d["delta"]["text"] for d in deltas)
        # C 端中文 refusal
        assert "Tevau 助手" in all_text

        # user 行 topic_verdict 已落库
        msgs = await conv_dao.list_messages(conv_id)
        user_rows = [m for m in msgs if m["role"] == "user"]
        assert user_rows[-1]["topic_verdict"] == "no"
        # 应有一条 assistant 文本（refusal 落库）
        assert any(m["role"] == "assistant" for m in msgs)

    async def test_yes_proceeds_to_main_llm(
        self,
        c_client: AsyncClient,
        conv_id: int,
        enable_classifier,
        mock_classify,
        fake_main_llm,
    ) -> None:
        mock_classify("yes")
        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "我卡为什么锁了"},
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        deltas = event_data(frames, "content_block_delta")
        all_text = "".join(d["delta"]["text"] for d in deltas)
        assert "ok" in all_text

        msgs = await conv_dao.list_messages(conv_id)
        user_rows = [m for m in msgs if m["role"] == "user"]
        assert user_rows[-1]["topic_verdict"] == "yes"

    async def test_uncertain_proceeds_with_hint(
        self,
        c_client: AsyncClient,
        conv_id: int,
        enable_classifier,
        mock_classify,
        monkeypatch,
    ) -> None:
        mock_classify("uncertain")
        # 捕获 build_messages_request 入参，确认 system 块多了 UNCERTAIN_HINT
        from ai_engine.agent import topic_classifier as tc
        from ai_engine.integrations import anthropic_client as _ac

        captured_systems: list[list[dict]] = []

        async def _fake_stream(req):
            captured_systems.append(req["system"])
            yield {
                "final": SimpleNamespace(
                    content=[SimpleNamespace(type="text", text="ok-uncertain")],
                    stop_reason="end_turn",
                    usage=SimpleNamespace(input_tokens=1, output_tokens=1),
                )
            }

        monkeypatch.setattr(_ac, "stream_turn", _fake_stream)

        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "API 卡片业务相关吗？"},
        )
        assert r.status_code == 200
        assert captured_systems, "stream_turn should have been called"
        flat = "".join(blk.get("text", "") for blk in captured_systems[0])
        assert tc.UNCERTAIN_HINT in flat

    async def test_classifier_error_fails_open_to_uncertain(
        self,
        c_client: AsyncClient,
        conv_id: int,
        enable_classifier,
        fake_main_llm,
        monkeypatch,
    ) -> None:
        """`classify` 内调的 anthropic_client.classify_topic 抛错 → fail-open 到 uncertain。

        注意：必须 patch _ac.classify_topic（而非顶层 topic_classifier.classify），后者的
        try/except 在自身实现里，外面 patch 掉就丢了 fail-open 语义。
        """
        from ai_engine.integrations import anthropic_client as _ac

        async def _boom(msg: str):
            raise RuntimeError("anthropic down")

        monkeypatch.setattr(_ac, "classify_topic", _boom)

        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "随便问问"},
        )
        assert r.status_code == 200
        msgs = await conv_dao.list_messages(conv_id)
        user_rows = [m for m in msgs if m["role"] == "user"]
        assert user_rows[-1]["topic_verdict"] == "uncertain"

    async def test_empty_message_skips_classification(
        self,
        c_client: AsyncClient,
        conv_id: int,
        enable_classifier,
        mock_classify,
        fake_main_llm,
    ) -> None:
        """纯空白消息 → 不分类（runtime 内 if message.strip()），verdict 列为 None。

        spec 注释：纯图片消息文本为空，无可分类，跳过视为放行。
        """
        # classify 一旦被调就报错（断言不应被调）
        from ai_engine.agent import topic_classifier as tc

        async def _shouldnt(msg: str):
            raise AssertionError("classify must not be called for empty text")

        # 必须放在 fake_main_llm 之后覆盖
        import pytest

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(tc, "classify", _shouldnt)
            r = await c_client.get(
                "/api/v1/chat",
                params={"conversation_id": conv_id, "message": "   "},
            )
            assert r.status_code == 200

        msgs = await conv_dao.list_messages(conv_id)
        user_rows = [m for m in msgs if m["role"] == "user"]
        assert user_rows[-1]["topic_verdict"] is None
