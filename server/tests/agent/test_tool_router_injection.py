"""Agent tool_router: 注入 conversation_id / user_type / unmask 字段

被测对象：
- NEEDS_CONVERSATION_ID 集合的工具（create_ticket）注入 conversation_id；其它工具不注入。
- NEEDS_USER_TYPE 集合的工具（create_ticket）注入 user_type。
- supports_unmask=True 的工具：客服代查 (unmask=True) 注入 unmask；AI 默认调用 (unmask=None) 不注入。
- supports_unmask=False 的工具：unmask 永远不注入，即使外部传 True。
- subject_field 不为 subject_id 时（如 tenant_id），注入键名正确。
"""

import pytest

from ai_engine.agent import tool_router as tr
from ai_engine.agent.tools import base as toolbase


@pytest.fixture
def _no_db_audit(monkeypatch):
    async def _noop(*_a, **_k):  # noqa: ANN002,ANN003
        return 0

    monkeypatch.setattr(tr, "log_tool_call", _noop)
    yield


@pytest.fixture
def _register_capture():
    """注册多个工具用于捕获 handler 收到的参数。"""
    captured: dict[str, list[dict]] = {}

    def _make(name: str, *, subject_field="user_id", supports_unmask=False, requires=True):
        captured[name] = []

        async def _h(**kw):  # noqa: ANN003
            captured[name].append(kw)
            return {"ok": True}

        toolbase.register(
            toolbase.Tool(
                name=name,
                description="x",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=_h,
                requires_subject_id=requires,
                subject_field=subject_field,
                supports_unmask=supports_unmask,
            )
        )
        return name

    yield _make, captured
    for n in list(captured.keys()):
        toolbase.REGISTRY.pop(n, None)


class TestConversationAndUserTypeInjection:
    """create_ticket 注入 conversation_id + user_type；其它工具不注入。"""

    async def test_create_ticket_gets_conversation_id_and_user_type(
        self, _no_db_audit, _register_capture
    ) -> None:
        make, captured = _register_capture
        # 用真名 create_ticket 触发 NEEDS_CONVERSATION_ID/NEEDS_USER_TYPE
        # 注意：要先 unregister 现有 create_ticket 再注册替身
        original = toolbase.REGISTRY.pop("create_ticket", None)
        try:
            make("create_ticket", subject_field="subject_id")
            await tr.dispatch(
                tool_name="create_ticket",
                params={"category": "bug"},
                user_type="b",
                subject_id="BU01",
                conversation_id=42,
            )
            kw = captured["create_ticket"][0]
            assert kw["conversation_id"] == 42
            assert kw["user_type"] == "b"
            assert kw["subject_id"] == "BU01"  # 身份注入 → subject_field
            assert kw["category"] == "bug"  # 用户参数保留
        finally:
            if original is not None:
                toolbase.REGISTRY["create_ticket"] = original

    async def test_other_tool_no_conversation_id(
        self, _no_db_audit, _register_capture
    ) -> None:
        make, captured = _register_capture
        make("other_tool", subject_field="user_id")
        await tr.dispatch(
            tool_name="other_tool",
            params={},
            user_type="c",
            subject_id="123",
            conversation_id=42,
        )
        kw = captured["other_tool"][0]
        assert "conversation_id" not in kw
        assert "user_type" not in kw
        assert kw["user_id"] == "123"


class TestUnmaskInjection:
    """unmask 注入规则：仅 supports_unmask + unmask=True 时注入 unmask=True；其余不注入。"""

    async def test_supports_unmask_true_inject_true(
        self, _no_db_audit, _register_capture
    ) -> None:
        make, captured = _register_capture
        make("masking_tool", supports_unmask=True)
        await tr.dispatch(
            tool_name="masking_tool",
            params={},
            user_type="c",
            subject_id="123",
            conversation_id=1,
            unmask=True,
        )
        assert captured["masking_tool"][0]["unmask"] is True

    async def test_supports_unmask_default_false_not_inject(
        self, _no_db_audit, _register_capture
    ) -> None:
        make, captured = _register_capture
        make("masking_tool", supports_unmask=True)
        # 默认 dispatch 不传 unmask → AI 自动调用，按 _resolve_ai_unmask=False
        await tr.dispatch(
            tool_name="masking_tool",
            params={},
            user_type="c",
            subject_id="123",
            conversation_id=1,
        )
        assert "unmask" not in captured["masking_tool"][0]

    async def test_supports_unmask_explicit_false_not_inject(
        self, _no_db_audit, _register_capture
    ) -> None:
        make, captured = _register_capture
        make("masking_tool", supports_unmask=True)
        await tr.dispatch(
            tool_name="masking_tool",
            params={},
            user_type="c",
            subject_id="123",
            conversation_id=1,
            unmask=False,
        )
        # 显式 False 不注入（语义：默认不解锁，无需写键）
        assert "unmask" not in captured["masking_tool"][0]

    async def test_not_supporting_unmask_strips_user_unmask(
        self, _no_db_audit, _register_capture
    ) -> None:
        make, captured = _register_capture
        make("plain_tool", supports_unmask=False)
        # 即便外部传 unmask=True，不支持的工具也不会拿到
        await tr.dispatch(
            tool_name="plain_tool",
            params={"unmask": True},
            user_type="c",
            subject_id="123",
            conversation_id=1,
            unmask=True,
        )
        assert "unmask" not in captured["plain_tool"][0]


class TestSubjectFieldInjection:
    """subject_field 决定身份注入的键名（user_id / tenant_id / subject_id 自定义）。"""

    async def test_tenant_id_field(self, _no_db_audit, _register_capture) -> None:
        make, captured = _register_capture
        make("bu_tool", subject_field="tenant_id")
        await tr.dispatch(
            tool_name="bu_tool",
            params={},
            user_type="b",
            subject_id="1011010000068",
            conversation_id=1,
        )
        kw = captured["bu_tool"][0]
        assert kw["tenant_id"] == "1011010000068"
        assert "user_id" not in kw

    async def test_subject_field_overwrites_user_param(
        self, _no_db_audit, _register_capture
    ) -> None:
        """AI 自己传 user_id（试图查别人）会被身份注入覆盖（防越权）。"""
        make, captured = _register_capture
        make("safe_tool", subject_field="user_id")
        await tr.dispatch(
            tool_name="safe_tool",
            params={"user_id": "OTHER_USER"},
            user_type="c",
            subject_id="100",
            conversation_id=1,
        )
        assert captured["safe_tool"][0]["user_id"] == "100"

    async def test_handler_receives_user_params_intact(
        self, _no_db_audit, _register_capture
    ) -> None:
        """与身份/conv 无关的业务参数应原样传到 handler。"""
        make, captured = _register_capture
        make("filter_tool", requires=False)
        await tr.dispatch(
            tool_name="filter_tool",
            params={"start": 10, "limit": 5, "kw": "abc"},
            user_type="c",
            subject_id="100",
            conversation_id=1,
        )
        kw = captured["filter_tool"][0]
        assert kw["start"] == 10 and kw["limit"] == 5 and kw["kw"] == "abc"
