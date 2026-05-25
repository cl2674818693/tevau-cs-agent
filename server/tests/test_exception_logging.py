"""A2: 静默吞掉异常处补日志（保留 fail-open 行为，但留下排障线索）。

用自挂 handler 捕获目标 logger 的记录，避免 caplog 受全套件 logging 全局状态干扰。
"""

import logging
from contextlib import contextmanager

import pytest

from ai_engine.agent import topic_classifier
from ai_engine.integrations import event_center_client as ec

pytestmark = pytest.mark.asyncio


@contextmanager
def capture(logger_name: str):
    records: list[logging.LogRecord] = []

    class _H(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(logger_name)
    handler = _H(level=logging.WARNING)
    prev_level, prev_disabled = logger.level, logging.root.manager.disable
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    logging.disable(logging.NOTSET)  # 抵消其他测试可能残留的 logging.disable
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)
        logging.disable(prev_disabled)


async def test_classify_logs_warning_on_failure(monkeypatch):
    async def boom(_message):
        raise RuntimeError("anthropic gateway down")

    monkeypatch.setattr(topic_classifier._ac, "classify_topic", boom)

    with capture("ai_engine.agent.topic_classifier") as records:
        verdict = await topic_classifier.classify("hello")

    assert verdict == "uncertain"  # fail-open 不变
    assert any(r.levelno >= logging.WARNING for r in records), "未记录 WARNING"


async def test_push_event_logs_warning_on_failure(monkeypatch):
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

    with capture("ai_engine.integrations.event_center_client") as records:
        ok = await ec.push_event_center({"type": "closed", "external_id": "T-1"})

    assert ok is False  # 失败不抛、返回 False 不变
    assert any(r.levelno >= logging.WARNING for r in records), "未记录 WARNING"
