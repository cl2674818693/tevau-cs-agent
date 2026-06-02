"""Agent tool_router: 权限/未知工具/游客降级

被测对象：tool_router.dispatch 在以下情况下的返回 + 落库审计：
- 未知工具 → {ok:False, error: "unknown tool: ..."}
- 游客(USER_TYPE_GUEST) + 需要 subject_id 的工具 → 引导登录回执（非业务执行）
- 游客 + 不要求 subject_id 的工具 → 放行
- subject 注入：handler 内拿到的 user_id/tenant_id 等于会话身份（_c_user_id 翻译 / 数字直接用）
"""

import pytest

from ai_engine.agent import tool_router as tr
from ai_engine.agent.tools import base as toolbase
from ai_engine.auth.bu_session import USER_TYPE_GUEST


@pytest.fixture
def _no_db_audit(monkeypatch):
    """tool_audits 表测试不关心：拦截 log_tool_call 直接 no-op，绕过 DB。"""

    async def _noop(*_a, **_k):  # noqa: ANN002,ANN003
        return 0

    monkeypatch.setattr(tr, "log_tool_call", _noop)
    yield


@pytest.fixture
def _register_tools():
    """注册一个 public_tool（不需要身份）+ private_tool（需要 user_id 注入）。"""
    captured: dict[str, list[dict]] = {"public": [], "private": []}

    async def _pub(**kw):  # noqa: ANN003
        captured["public"].append(kw)
        return {"ok": True}

    async def _priv(**kw):  # noqa: ANN003
        captured["private"].append(kw)
        return {"got_user_id": kw.get("user_id")}

    toolbase.register(
        toolbase.Tool(
            name="public_tool",
            description="x",
            input_schema={"type": "object", "properties": {}, "required": []},
            handler=_pub,
        )
    )
    toolbase.register(
        toolbase.Tool(
            name="private_tool",
            description="x",
            input_schema={"type": "object", "properties": {}, "required": []},
            handler=_priv,
            requires_subject_id=True,
            subject_field="user_id",
        )
    )
    yield captured
    toolbase.REGISTRY.pop("public_tool", None)
    toolbase.REGISTRY.pop("private_tool", None)


class TestUnknownTool:
    """未知工具：ok=False，error 含 'unknown tool'，并落 audit（被 mock）。"""

    async def test_unknown_tool_returns_error(self, _no_db_audit) -> None:
        out = await tr.dispatch(
            tool_name="this_tool_does_not_exist",
            params={},
            user_type="c",
            subject_id="123",
            conversation_id=1,
        )
        assert out["ok"] is False
        assert "unknown tool" in out["error"]


class TestGuestDowngrade:
    """游客身份：requires_subject_id 的工具被拒，且返回引导登录文案。"""

    async def test_guest_blocked_on_private_tool(
        self, _no_db_audit, _register_tools
    ) -> None:
        out = await tr.dispatch(
            tool_name="private_tool",
            params={},
            user_type=USER_TYPE_GUEST,
            subject_id="anon",
            conversation_id=1,
        )
        assert out["ok"] is False
        assert "登录" in out["error"]
        # handler 没有被调用到
        assert _register_tools["private"] == []

    async def test_guest_can_use_public_tool(
        self, _no_db_audit, _register_tools
    ) -> None:
        out = await tr.dispatch(
            tool_name="public_tool",
            params={},
            user_type=USER_TYPE_GUEST,
            subject_id="anon",
            conversation_id=1,
        )
        assert out["ok"] is True
        assert _register_tools["public"], "public_tool 应被调用"


class TestSubjectInjectionNumeric:
    """B 端 tenant 是数字 / C 端 user_id 已是纯数字时直接注入，不打业务库翻译。"""

    async def test_b_user_tenant_id_passthrough(
        self, _no_db_audit, _register_tools
    ) -> None:
        # private_tool 声明 subject_field=user_id，但 B 端这里只测注入而非语义
        out = await tr.dispatch(
            tool_name="private_tool",
            params={},
            user_type="b",
            subject_id="1011010000068",
            conversation_id=1,
        )
        assert out["ok"] is True
        assert _register_tools["private"][0]["user_id"] == "1011010000068"

    async def test_c_numeric_user_id_passthrough(
        self, _no_db_audit, _register_tools
    ) -> None:
        out = await tr.dispatch(
            tool_name="private_tool",
            params={},
            user_type="c",
            subject_id="123456",  # 纯数字 → 不翻译
            conversation_id=1,
        )
        assert out["ok"] is True
        assert _register_tools["private"][0]["user_id"] == "123456"

    async def test_ai_traffic_cannot_force_unmask(
        self, _no_db_audit, _register_tools
    ) -> None:
        """AI 自调用：传 unmask=True 也会被 _resolve_ai_unmask 干掉为 False；
        不声明 supports_unmask 的工具不会注入 unmask。"""
        out = await tr.dispatch(
            tool_name="private_tool",
            params={"unmask": True},  # AI 想强行解锁
            user_type="c",
            subject_id="123",
            conversation_id=1,
        )
        assert out["ok"] is True
        # private_tool 不声明 supports_unmask → 不应有 unmask 字段
        assert "unmask" not in _register_tools["private"][0]


class TestValueErrorAsBadArgs:
    """handler raise ValueError → 标 invalid args（区别于 internal error）。"""

    async def test_value_error_becomes_invalid_args(self, _no_db_audit) -> None:
        async def _bad(**_k):
            raise ValueError("category must be one of [...]")

        toolbase.register(
            toolbase.Tool(
                name="strict_tool",
                description="x",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=_bad,
            )
        )
        try:
            out = await tr.dispatch(
                tool_name="strict_tool",
                params={},
                user_type="c",
                subject_id="1",
                conversation_id=1,
            )
            assert out["ok"] is False
            assert out["error"].startswith("invalid args")
        finally:
            toolbase.REGISTRY.pop("strict_tool", None)

    async def test_generic_exception_returns_internal_error_text(
        self, _no_db_audit
    ) -> None:
        async def _boom(**_k):
            raise RuntimeError("internals")

        toolbase.register(
            toolbase.Tool(
                name="boom_tool",
                description="x",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=_boom,
            )
        )
        try:
            out = await tr.dispatch(
                tool_name="boom_tool",
                params={},
                user_type="c",
                subject_id="1",
                conversation_id=1,
            )
            assert out["ok"] is False
            # 异常细节不外泄给 AI（更不会给前端）
            assert out["error"] == "internal error"
            assert "internals" not in out["error"]
        finally:
            toolbase.REGISTRY.pop("boom_tool", None)


class TestResultCountHelper:
    """_result_count：count* 字段优先 / list 长度兜底 / 元字段 note/unmasked 不计。"""

    def test_count_keys_summed(self) -> None:
        assert tr._result_count({"card_count": 2, "wallet_count": 3}) == 5

    def test_lists_summed_when_no_count(self) -> None:
        assert tr._result_count({"hits": [1, 2, 3], "errors": [4]}) == 4

    def test_meta_fields_excluded(self) -> None:
        assert tr._result_count({"note": "x", "unmasked": False}) == 0

    def test_non_dict_truthy_one(self) -> None:
        assert tr._result_count(["x"]) == 1
        assert tr._result_count(0) == 0

    def test_records_present_returns_one(self) -> None:
        assert tr._result_count({"user": {"id": 1}}) == 1
