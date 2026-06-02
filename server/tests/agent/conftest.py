"""agent 子目录共享夹具：runtime 跑前清掉一系列全局状态/缓存，避免互相污染。

- prompt registry 缓存 / loader 缓存 / tool_router 的 C 端 user_code 缓存。
- 关闭 topic_classifier（runtime 默认关；少数测试用 monkeypatch 显式开）。
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _clean_prompt_caches(monkeypatch):
    """每个用例前清空 prompt registry / loader 缓存，确保 reload_registry 类用例隔离。"""
    from ai_engine.agent.tool_router import _c_user_id_cache
    from ai_engine.prompts import loader, registry as preg

    preg.reload_registry()
    loader.clear_cache()
    _c_user_id_cache.clear()
    yield


@pytest.fixture
def make_resp():
    """构造 anthropic Message 替身（含 content/stop_reason/usage）。

    tool_calls 形如 [{"id": "t1", "name": "query_user", "input": {...}}]，会拼成 tool_use 块。
    """

    def _make(
        text: str = "",
        tool_calls: list[dict[str, Any]] | None = None,
        stop_reason: str = "end_turn",
        input_tokens: int = 10,
        output_tokens: int = 5,
    ) -> MagicMock:
        content: list[MagicMock] = []
        if text:
            tb = MagicMock(type="text")
            tb.text = text  # MagicMock 直接构造 text= 会被当成 spec，显式赋值更稳
            content.append(tb)
        for tc in tool_calls or []:
            ub = MagicMock(type="tool_use")
            ub.id = tc["id"]
            ub.name = tc["name"]
            ub.input = tc.get("input", {})
            content.append(ub)
        usage = MagicMock()
        usage.input_tokens = input_tokens
        usage.output_tokens = output_tokens
        m = MagicMock()
        m.content = content
        m.stop_reason = stop_reason
        m.usage = usage
        return m

    return _make
