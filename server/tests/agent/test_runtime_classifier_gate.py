"""Agent runtime: topic_classifier 拦截

被测对象：
- topic_classifier.classify：yes/no/uncertain 判定 + 异常 fail-open。
- runtime 启用 classifier 时：no 直接 refusal 并结束；uncertain 注入 hint；yes 正常走。
"""

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.agent import topic_classifier
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence.conversations import create_conversation, list_messages


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}

    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


class TestClassifyVerdictParsing:
    """classify_topic 文本 → 三态 verdict 解析。"""

    async def test_yes_prefix(self, monkeypatch) -> None:
        async def _ret(_msg):
            return "YES"

        monkeypatch.setattr(_ac, "classify_topic", _ret)
        assert await topic_classifier.classify("hi") == "yes"

    async def test_no_prefix(self, monkeypatch) -> None:
        async def _ret(_msg):
            return "no, off-topic"

        monkeypatch.setattr(_ac, "classify_topic", _ret)
        assert await topic_classifier.classify("hi") == "no"

    async def test_uncertain_default(self, monkeypatch) -> None:
        async def _ret(_msg):
            return "uncertain reasoning..."

        monkeypatch.setattr(_ac, "classify_topic", _ret)
        assert await topic_classifier.classify("hi") == "uncertain"

    async def test_garbage_defaults_to_uncertain(self, monkeypatch) -> None:
        async def _ret(_msg):
            return "maybe"

        monkeypatch.setattr(_ac, "classify_topic", _ret)
        assert await topic_classifier.classify("hi") == "uncertain"

    async def test_failure_fail_open_to_uncertain(self, monkeypatch) -> None:
        async def _boom(_msg):
            raise RuntimeError("api down")

        monkeypatch.setattr(_ac, "classify_topic", _boom)
        # fail-open：异常时归为 uncertain（不抛、不阻断）
        assert await topic_classifier.classify("hi") == "uncertain"


class TestRefusalText:
    """i18n 化后：C/B 端共享同一 key，语言由 ui_locale 决定（B 端默认 en，C 端跟随 APP）。"""

    def test_refusal_c_chinese_when_zh_locale(self) -> None:
        msg = topic_classifier.refusal_text("c", "zh-Hant")
        assert "Tevau" in msg
        assert "助手" in msg

    def test_refusal_b_english_default(self) -> None:
        msg = topic_classifier.refusal_text("b")
        assert "Tevau" in msg
        assert "Open API" in msg

    def test_unknown_user_type_resolves(self) -> None:
        # user_type 不再决定文案，refusal_text 一律返回非空
        msg = topic_classifier.refusal_text("x")
        assert msg and "Tevau" in msg


class TestRuntimeClassifierGate:
    """启用 classifier 后：no 直接出 refusal 并结束；uncertain/yes 走主 LLM。"""

    async def test_no_verdict_emits_refusal_no_llm_call(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "topic_classifier_enabled", True)

        async def _cls(_msg):
            return "no"

        monkeypatch.setattr(topic_classifier, "classify", _cls)

        # 若主 LLM 被调用即测试失败（应当被 classifier 截断）
        def _stream(**_kw):
            raise AssertionError("main LLM must not be called on verdict=no")

        monkeypatch.setattr(_ac._client.messages, "stream", _stream)
        _ = fake_stream, make_resp  # silence imports

        conv = await create_conversation("c", "U001")
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="今天天气",
            )
        ]
        # 单次 text 事件，为 refusal 文案
        assert len(events) == 1
        assert events[0]["type"] == "text"
        assert "Tevau" in events[0]["text"]
        # turn 已 done；topic_verdict=no 落入 user 行
        msgs = await list_messages(conv)
        user_rows = [m for m in msgs if m["role"] == "user"]
        assert user_rows[-1]["topic_verdict"] == "no"
        assert user_rows[-1]["status"] == "done"
        # 同时入库 1 条 assistant=refusal
        assert any(m["role"] == "assistant" for m in msgs)

    async def test_uncertain_verdict_still_calls_llm(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "topic_classifier_enabled", True)

        async def _cls(_msg):
            return "uncertain"

        monkeypatch.setattr(topic_classifier, "classify", _cls)
        monkeypatch.setattr(
            _ac._client.messages,
            "stream",
            fake_stream([make_resp(text="ok"), make_resp(text="ok")]),
        )

        conv = await create_conversation("c", "U001")
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="不确定 query",
            )
        ]
        # 主 LLM 正常出文本
        assert any(e.get("type") == "text" for e in events)
        msgs = await list_messages(conv)
        user_rows = [m for m in msgs if m["role"] == "user"]
        assert user_rows[-1]["topic_verdict"] == "uncertain"

    async def test_yes_verdict_passes_through(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "topic_classifier_enabled", True)

        async def _cls(_msg):
            return "yes"

        monkeypatch.setattr(topic_classifier, "classify", _cls)
        monkeypatch.setattr(
            _ac._client.messages,
            "stream",
            fake_stream([make_resp(text="ok"), make_resp(text="ok")]),
        )

        conv = await create_conversation("c", "U001")
        async for _ in rt.run_turn(
            conversation_id=conv,
            user_type="c",
            subject_id="U001",
            user_message="查余额",
        ):
            pass
        msgs = await list_messages(conv)
        user_rows = [m for m in msgs if m["role"] == "user"]
        assert user_rows[-1]["topic_verdict"] == "yes"

    async def test_classifier_disabled_skips_classify_call(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "topic_classifier_enabled", False)

        async def _cls(_msg):
            raise AssertionError("classifier should not be called when disabled")

        monkeypatch.setattr(topic_classifier, "classify", _cls)
        monkeypatch.setattr(
            _ac._client.messages,
            "stream",
            fake_stream([make_resp(text="x"), make_resp(text="x")]),
        )
        conv = await create_conversation("c", "U001")
        async for _ in rt.run_turn(
            conversation_id=conv,
            user_type="c",
            subject_id="U001",
            user_message="hi",
        ):
            pass
        msgs = await list_messages(conv)
        user_rows = [m for m in msgs if m["role"] == "user"]
        # topic_verdict 不应被写入
        assert user_rows[-1]["topic_verdict"] is None
