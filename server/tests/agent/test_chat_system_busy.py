"""B1: SystemBusy 必须映射为 SYSTEM_BUSY SSE 事件，不应被 INTERNAL_ERROR 吞掉。

测试策略：把 chat.gen() 的所有外部依赖 stub 掉，让 _stream_ai_turn 抛 SystemBusy，
直接驱动 chat() 返回的 EventSourceResponse.body_iterator，断言：
- 出现 event=error code=SYSTEM_BUSY 帧
- 不再出现 INTERNAL_ERROR
"""
import asyncio
import json

import pytest

from ai_engine.api import chat as chat_api
from ai_engine.integrations.anthropic_client import SystemBusy


class _FakeRequest:
    """最小 Request 替身：chat() 只读 client.host / is_disconnected。"""

    def __init__(self) -> None:
        self.client = type("c", (), {"host": "127.0.0.1"})()

    async def is_disconnected(self) -> bool:
        return False


async def _drive_gen(monkeypatch, raised_exc: BaseException) -> list[dict[str, str]]:
    """把 _stream_ai_turn 替换成抛 raised_exc 的 async generator，驱动 chat()。

    返回 chat() yield 出的所有 SSE 帧 dict（{"event":..., "data":...}）。
    """
    # _stream_ai_turn 是 async generator —— 必须先 yield 一次进入 generator 协议，再 raise
    async def boom(*_a, **_kw):
        raise raised_exc
        yield  # noqa: B901  pragma: no cover  让函数被识别为 async generator

    monkeypatch.setattr(chat_api, "_stream_ai_turn", boom)

    # 短路 chat() 入口前置：身份 / mode / token_budget / rate_limit / 幂等查询
    async def _ok_authorize(*_a, **_kw):
        return ("c", "U-TEST")

    monkeypatch.setattr(chat_api, "_authorize_conversation", _ok_authorize)

    async def _no_block(*_a, **_kw):
        return None

    monkeypatch.setattr(chat_api, "_early_block", _no_block)

    async def _no_dup(*_a, **_kw):
        return None

    monkeypatch.setattr(chat_api, "_duplicate_turn_id", _no_dup)

    async def _ai_mode(*_a, **_kw):
        return ("ai", None)

    monkeypatch.setattr(chat_api.conv_dao, "get_mode", _ai_mode)

    async def _not_exhausted(*_a, **_kw):
        return False

    monkeypatch.setattr(chat_api.token_budget, "is_exhausted", _not_exhausted)

    # 跨 worker cancel listener：默认 redis 未配置直接返回 None
    monkeypatch.setattr(chat_api.rate_limit, "_get_redis", lambda: None, raising=False)

    req = _FakeRequest()
    resp = await chat_api.chat(
        request=req,
        conversation_id=42,
        message="hi",
        client_message_id=None,
        attachment_ids=None,
        ui_locale="zh",
        last_event_id=None,
    )

    frames: list[dict[str, str]] = []
    # EventSourceResponse.body_iterator 是 chat.gen() 的 async generator
    async for frame in resp.body_iterator:
        if isinstance(frame, dict):
            frames.append(frame)
        if len(frames) > 20:
            break
    return frames


async def test_system_busy_yields_specific_event(monkeypatch):
    frames = await _drive_gen(monkeypatch, SystemBusy("semaphore full"))

    error_frames = [f for f in frames if f.get("event") == "error"]
    assert error_frames, f"expected error event, got frames: {frames}"
    payload = json.loads(error_frames[0]["data"])
    assert payload["code"] == "SYSTEM_BUSY", (
        f"expected SYSTEM_BUSY, got {payload.get('code')}; frames={frames}"
    )
    # zh locale: "系统繁忙，稍后重试。"
    assert "繁忙" in payload["message"]


async def test_generic_exception_still_yields_internal_error(monkeypatch):
    """回归：除 SystemBusy 以外的异常仍走 INTERNAL_ERROR 分支。"""
    frames = await _drive_gen(monkeypatch, RuntimeError("boom"))

    error_frames = [f for f in frames if f.get("event") == "error"]
    assert error_frames, f"expected error event, got frames: {frames}"
    payload = json.loads(error_frames[0]["data"])
    assert payload["code"] == "INTERNAL_ERROR", (
        f"expected INTERNAL_ERROR for generic exc, got {payload.get('code')}"
    )


async def test_system_busy_uses_english_for_en_locale(monkeypatch):
    """i18n: ui_locale=en 时返回英文文案。"""

    async def boom(*_a, **_kw):
        raise SystemBusy("full")
        yield

    monkeypatch.setattr(chat_api, "_stream_ai_turn", boom)

    async def _ok_authorize(*_a, **_kw):
        return ("c", "U-TEST")

    monkeypatch.setattr(chat_api, "_authorize_conversation", _ok_authorize)

    async def _no_block(*_a, **_kw):
        return None

    monkeypatch.setattr(chat_api, "_early_block", _no_block)

    async def _no_dup(*_a, **_kw):
        return None

    monkeypatch.setattr(chat_api, "_duplicate_turn_id", _no_dup)

    async def _ai_mode(*_a, **_kw):
        return ("ai", None)

    monkeypatch.setattr(chat_api.conv_dao, "get_mode", _ai_mode)

    async def _not_exhausted(*_a, **_kw):
        return False

    monkeypatch.setattr(chat_api.token_budget, "is_exhausted", _not_exhausted)
    monkeypatch.setattr(chat_api.rate_limit, "_get_redis", lambda: None, raising=False)

    resp = await chat_api.chat(
        request=_FakeRequest(),
        conversation_id=1,
        message="hi",
        client_message_id=None,
        attachment_ids=None,
        ui_locale="en",
        last_event_id=None,
    )
    frames = []
    async for f in resp.body_iterator:
        if isinstance(f, dict):
            frames.append(f)
        if len(frames) > 20:
            break
    err = next(f for f in frames if f.get("event") == "error")
    payload = json.loads(err["data"])
    assert payload["code"] == "SYSTEM_BUSY"
    assert "busy" in payload["message"].lower()
