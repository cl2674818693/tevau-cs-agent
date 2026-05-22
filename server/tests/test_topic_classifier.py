import pytest


async def test_classify_parses_three_states(monkeypatch):
    from ai_engine.agent import topic_classifier
    from ai_engine.integrations import anthropic_client as ac

    async def fake(word):
        return word

    monkeypatch.setattr(ac, "classify_topic", lambda m: fake("YES"))
    assert await topic_classifier.classify("绑卡失败") == "yes"
    monkeypatch.setattr(ac, "classify_topic", lambda m: fake("no"))
    assert await topic_classifier.classify("帮我写首诗") == "no"
    monkeypatch.setattr(ac, "classify_topic", lambda m: fake("uncertain"))
    assert await topic_classifier.classify("在吗") == "uncertain"


async def test_classify_fails_open_to_uncertain(monkeypatch):
    from ai_engine.agent import topic_classifier
    from ai_engine.integrations import anthropic_client as ac

    async def boom(m):
        raise RuntimeError("haiku down")

    monkeypatch.setattr(ac, "classify_topic", boom)
    assert await topic_classifier.classify("x") == "uncertain"


def test_refusal_text_by_user_type():
    from ai_engine.agent import topic_classifier

    assert "Tevau 助手" in topic_classifier.refusal_text("c")
    assert "Tevau's support assistant" in topic_classifier.refusal_text("b")


@pytest.mark.parametrize("user_type,needle", [("c", "Tevau 助手"), ("b", "support assistant")])
async def test_run_turn_no_verdict_short_circuits(seeded_db, monkeypatch, user_type, needle):
    """分类 no → 直接 refusal，不进主 agent loop（不调 messages.create）。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("TOPIC_CLASSIFIER_ENABLED", "true")
    from ai_engine.agent import runtime, topic_classifier
    from ai_engine.config import settings

    settings.reload()

    async def fake_classify(_msg):
        return "no"

    monkeypatch.setattr(topic_classifier, "classify", fake_classify)

    called = {"loop": False}

    def boom(**kw):
        called["loop"] = True
        raise AssertionError("主 agent loop 不应被调用")

    monkeypatch.setattr(runtime._ac._client.messages, "create", boom)

    texts = []
    async for ev in runtime.run_turn(
        conversation_id=1, user_type=user_type, subject_id="S1", user_message="帮我写代码"
    ):
        if ev.get("type") == "text":
            texts.append(ev["text"])

    settings.reload()
    assert called["loop"] is False
    assert any(needle in t for t in texts)
