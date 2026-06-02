"""Agent tool_router: C 端身份翻译（userCode → 数字 user_id）

被测对象：tool_router._c_user_id + dispatch 在 user_type='c' & subject_id 非纯数字时
打 unlimitpay 业务库查 t_tevaupay_user.id，注入到 subject_field。

mock 策略：
- 用 monkeypatch 替换 get_db("unlimitpay") 为内存假对象（fetch_one 返回固定行）。
- 命中：注入数字 id 给 handler。
- 未命中：返回 error，handler 不被调用。
- 缓存：第二次调用同一 user_code 不再打库。
- 纯数字 subject_id：直接注入，不打库。
"""

import pytest

from ai_engine.agent import tool_router as tr
from ai_engine.agent.tools import base as toolbase
from ai_engine.persistence import business_db as bdb


class _FakeBusinessDB:
    """假业务库：按 (sql, params) 列表回放 fetch_one。"""

    def __init__(self, rows: dict[tuple, dict | None]) -> None:
        self.rows = rows
        self.calls: list[tuple] = []

    async def fetch_one(self, sql: str, params: tuple) -> dict | None:
        self.calls.append((sql, params))
        return self.rows.get(params)

    async def fetch_all(self, *_a, **_k):  # noqa: ANN002,ANN003
        return []


@pytest.fixture
def _no_db_audit(monkeypatch):
    async def _noop(*_a, **_k):  # noqa: ANN002,ANN003
        return 0

    monkeypatch.setattr(tr, "log_tool_call", _noop)
    yield


@pytest.fixture
def _patch_unlimitpay(monkeypatch):
    """把 get_db('unlimitpay') 替成假 DB；返回 fake 实例供测试断言 calls。"""
    fake = _FakeBusinessDB(rows={})

    def _get(name: str):
        assert name == "unlimitpay"
        return fake

    monkeypatch.setattr(bdb, "get_db", _get)
    # tool_router._c_user_id 内通过 from ai_engine.persistence.business_db import get_db 直接拿
    # 必须 patch 模块属性
    monkeypatch.setattr(tr, "get_db", _get, raising=False)
    yield fake


@pytest.fixture
def _capture_tool():
    captured: list[dict] = []

    async def _h(**kw):  # noqa: ANN003
        captured.append(kw)
        return {"ok": True, "got": kw.get("user_id")}

    toolbase.register(
        toolbase.Tool(
            name="ident_tool",
            description="x",
            input_schema={"type": "object", "properties": {}, "required": []},
            handler=_h,
            requires_subject_id=True,
            subject_field="user_id",
        )
    )
    yield captured
    toolbase.REGISTRY.pop("ident_tool", None)


class TestCUserCodeTranslation:
    """userCode（带字母前缀）→ 数字 user_id 翻译。"""

    async def test_user_code_translated_then_injected(
        self, _no_db_audit, _patch_unlimitpay, _capture_tool
    ) -> None:
        _patch_unlimitpay.rows = {("U43825474",): {"id": 100200}}

        out = await tr.dispatch(
            tool_name="ident_tool",
            params={},
            user_type="c",
            subject_id="U43825474",
            conversation_id=1,
        )
        assert out["ok"] is True
        assert _capture_tool[0]["user_id"] == "100200"
        # 业务库被打了一次
        assert len(_patch_unlimitpay.calls) == 1

    async def test_user_code_cached(
        self, _no_db_audit, _patch_unlimitpay, _capture_tool
    ) -> None:
        """第二次同 userCode 不再打业务库（命中进程缓存）。"""
        _patch_unlimitpay.rows = {("U43825474",): {"id": 100200}}

        await tr.dispatch(
            tool_name="ident_tool",
            params={},
            user_type="c",
            subject_id="U43825474",
            conversation_id=1,
        )
        await tr.dispatch(
            tool_name="ident_tool",
            params={},
            user_type="c",
            subject_id="U43825474",
            conversation_id=1,
        )
        assert len(_patch_unlimitpay.calls) == 1  # 第 2 次走 cache

    async def test_user_code_unmapped_returns_error(
        self, _no_db_audit, _patch_unlimitpay, _capture_tool
    ) -> None:
        # 假库没这个 user_code → fetch_one 返回 None
        _patch_unlimitpay.rows = {}

        out = await tr.dispatch(
            tool_name="ident_tool",
            params={},
            user_type="c",
            subject_id="U999",
            conversation_id=1,
        )
        assert out["ok"] is False
        assert "映射" in out["error"] or "转人工" in out["error"]
        # handler 不应被调用
        assert _capture_tool == []

    async def test_user_code_row_with_null_id_treated_as_unmapped(
        self, _no_db_audit, _patch_unlimitpay, _capture_tool
    ) -> None:
        _patch_unlimitpay.rows = {("U999",): {"id": None}}

        out = await tr.dispatch(
            tool_name="ident_tool",
            params={},
            user_type="c",
            subject_id="U999",
            conversation_id=1,
        )
        assert out["ok"] is False
        assert _capture_tool == []


class TestNumericSubjectIdShortcut:
    """subject_id 已是纯数字 → 直接注入，不打业务库（即便 patch 准备了 row 也不会调）。"""

    async def test_numeric_subject_id_no_db(
        self, _no_db_audit, _patch_unlimitpay, _capture_tool
    ) -> None:
        await tr.dispatch(
            tool_name="ident_tool",
            params={},
            user_type="c",
            subject_id="123456",
            conversation_id=1,
        )
        assert _capture_tool[0]["user_id"] == "123456"
        assert _patch_unlimitpay.calls == []


class TestBUserTypeNotTranslated:
    """B 端 / 游客等 user_type 不走 C 端翻译路径（即便 subject_id 含字母）。"""

    async def test_b_user_type_passthrough(
        self, _no_db_audit, _patch_unlimitpay, _capture_tool
    ) -> None:
        # B 端 subject_id 包含字母（很少见，但 _c_user_id 不应被触发）
        await tr.dispatch(
            tool_name="ident_tool",
            params={},
            user_type="b",
            subject_id="BU00243780",
            conversation_id=1,
        )
        assert _capture_tool[0]["user_id"] == "BU00243780"
        assert _patch_unlimitpay.calls == []
