"""Agent tool_router: 工具结果数量统计

被测对象：tool_router._result_count + dispatch 在 tool_audits 中写入 result_count/is_empty。
覆盖维度：
- *count* 整数键之和优先
- list 长度之和（无 count 键）
- 元字段 note/unmasked/pii_note 不计
- 非 dict 时 truthy = 1，falsy = 0
- 空对象 / 空 list 均为 0
- dispatch 成功路径下 audit 行 result_count == _result_count(data)，is_empty 与 rc==0 一致
"""

import pytest

from ai_engine.agent import tool_router as tr
from ai_engine.agent.tools import base as toolbase


class TestResultCountPure:
    """_result_count 纯函数矩阵。"""

    @pytest.mark.parametrize(
        "data, expected",
        [
            ({"card_count": 0, "wallet_count": 0}, 0),  # count 都为 0
            ({"card_count": 1, "wallet_count": 2}, 3),  # 求和
            ({"count": 10}, 10),  # 单 count
            ({"hits": []}, 0),  # 空 list
            ({"hits": ["a", "b"]}, 2),  # 2 个
            ({"hits": ["a"], "errors": ["e1", "e2"]}, 3),  # 多 list 求和
            ({"note": "x"}, 0),  # 元字段不计
            ({"unmasked": True, "pii_note": "y"}, 0),
            ({"user": {"id": 1}}, 1),  # 单记录视为 1
            ({}, 0),  # 完全空
            (None, 0),
            ("", 0),
            (0, 0),
            ([], 0),
            (["x"], 1),
            ("anything", 1),
        ],
    )
    def test_matrix(self, data, expected: int) -> None:
        assert tr._result_count(data) == expected


class TestDispatchAuditWritesResultCount:
    """dispatch 成功路径下，传给 log_tool_call 的 result_count/is_empty 一致。"""

    async def test_audit_captures_result_count_nonempty(self, monkeypatch) -> None:
        async def _h(**_kw):  # noqa: ANN003
            return {"hits": ["a", "b", "c"]}

        toolbase.register(
            toolbase.Tool(
                name="rc_tool",
                description="x",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=_h,
            )
        )
        captured: list[dict] = []

        async def _log(*_a, **kw):  # noqa: ANN002,ANN003
            captured.append(kw)
            return 0

        monkeypatch.setattr(tr, "log_tool_call", _log)
        try:
            out = await tr.dispatch(
                tool_name="rc_tool",
                params={},
                user_type="c",
                subject_id="1",
                conversation_id=1,
            )
            assert out["ok"] is True
            row = captured[-1]
            assert row["result_count"] == 3
            assert row["is_empty"] is False
        finally:
            toolbase.REGISTRY.pop("rc_tool", None)

    async def test_audit_captures_empty_flag(self, monkeypatch) -> None:
        async def _h(**_kw):  # noqa: ANN003
            return {"hits": [], "note": "empty"}

        toolbase.register(
            toolbase.Tool(
                name="rc_empty",
                description="x",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=_h,
            )
        )
        captured: list[dict] = []

        async def _log(*_a, **kw):  # noqa: ANN002,ANN003
            captured.append(kw)
            return 0

        monkeypatch.setattr(tr, "log_tool_call", _log)
        try:
            await tr.dispatch(
                tool_name="rc_empty",
                params={},
                user_type="c",
                subject_id="1",
                conversation_id=1,
            )
            row = captured[-1]
            assert row["result_count"] == 0
            assert row["is_empty"] is True
        finally:
            toolbase.REGISTRY.pop("rc_empty", None)

    async def test_failure_audit_marks_empty(self, monkeypatch) -> None:
        """异常路径：result_count=0, is_empty=True 必写入。"""

        async def _h(**_kw):
            raise ValueError("bad")

        toolbase.register(
            toolbase.Tool(
                name="rc_fail",
                description="x",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=_h,
            )
        )
        captured: list[dict] = []

        async def _log(*_a, **kw):  # noqa: ANN002,ANN003
            captured.append(kw)
            return 0

        monkeypatch.setattr(tr, "log_tool_call", _log)
        try:
            out = await tr.dispatch(
                tool_name="rc_fail",
                params={},
                user_type="c",
                subject_id="1",
                conversation_id=1,
            )
            assert out["ok"] is False
            row = captured[-1]
            assert row["result_count"] == 0
            assert row["is_empty"] is True
        finally:
            toolbase.REGISTRY.pop("rc_fail", None)
