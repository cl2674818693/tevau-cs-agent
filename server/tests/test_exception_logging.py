"""A2: 静默吞掉异常处补日志（保留 fail-open 行为，但留下排障线索）。"""

import logging

import pytest

from ai_engine.agent import topic_classifier
from ai_engine.integrations import event_center_client as ec

pytestmark = pytest.mark.asyncio


async def test_classify_logs_warning_on_failure(monkeypatch, caplog):
    async def boom(_message):
        raise RuntimeError("anthropic gateway down")

    monkeypatch.setattr(topic_classifier._ac, "classify_topic", boom)

    with caplog.at_level(logging.WARNING):
        verdict = await topic_classifier.classify("hello")

    assert verdict == "uncertain"  # fail-open 不变
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("topic" in r.name.lower() for r in warnings), [r.name for r in warnings]


async def test_push_event_logs_warning_on_failure(monkeypatch, caplog):
    class _BoomClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(ec.httpx, "AsyncClient", _BoomClient)

    with caplog.at_level(logging.WARNING):
        ok = await ec.push_event_center({"type": "closed", "external_id": "T-1"})

    assert ok is False  # 失败不抛、返回 False 不变
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("event_center" in r.name.lower() for r in warnings), [r.name for r in warnings]
