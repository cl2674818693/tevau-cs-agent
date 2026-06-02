"""Unit tests: governance.token_budget

被测对象：日 token 上限治理（spec §8）。is_exhausted 入口硬闸；
check_and_record 拒绝/通过/警告，按自然日 UTC 累计。
mock 策略：monkeypatch _get_used / _record，避免任何真实 DB 调用。
"""

from typing import Any

import pytest

from ai_engine.governance import token_budget as tb


def _patch_usage(monkeypatch, used_in: int, used_out: int) -> dict[str, Any]:
    """伪造 _get_used 返回固定累计；同时记录 _record 是否被调用。"""
    state: dict[str, Any] = {"recorded": []}

    async def _gu(_sid: str, _ut: str, _day: str) -> tuple[int, int]:
        return used_in, used_out

    async def _rec(sid: str, ut: str, day: str, it: int, ot: int, model: str | None = None) -> None:
        state["recorded"].append(
            {"sid": sid, "ut": ut, "day": day, "in": it, "out": ot, "model": model}
        )

    monkeypatch.setattr(tb, "_get_used", _gu)
    monkeypatch.setattr(tb, "_record", _rec)
    return state


class TestIsExhausted:
    """is_exhausted：当日已用 >= 阈值则 True，否则 False。"""

    async def test_under_limit_returns_false(self, monkeypatch) -> None:
        _patch_usage(monkeypatch, 100, 100)
        assert await tb.is_exhausted("c", "u-1") is False

    async def test_zero_usage_returns_false(self, monkeypatch) -> None:
        _patch_usage(monkeypatch, 0, 0)
        assert await tb.is_exhausted("c", "u-1") is False

    async def test_at_limit_returns_true(self, monkeypatch) -> None:
        limit = int(tb.settings.daily_token_limit)
        _patch_usage(monkeypatch, limit, 0)
        assert await tb.is_exhausted("c", "u-1") is True

    async def test_just_below_limit_returns_false(self, monkeypatch) -> None:
        limit = int(tb.settings.daily_token_limit)
        _patch_usage(monkeypatch, limit - 1, 0)
        assert await tb.is_exhausted("c", "u-1") is False

    async def test_above_limit_returns_true(self, monkeypatch) -> None:
        limit = int(tb.settings.daily_token_limit)
        _patch_usage(monkeypatch, limit, 1000)
        assert await tb.is_exhausted("c", "u-1") is True

    async def test_dao_failure_propagates(self, monkeypatch) -> None:
        async def _boom(*_a: Any) -> tuple[int, int]:
            raise RuntimeError("db down")

        monkeypatch.setattr(tb, "_get_used", _boom)
        with pytest.raises(RuntimeError, match="db down"):
            await tb.is_exhausted("c", "u-1")


class TestCheckAndRecordRejection:
    """已达上限：返回 (False, info)，不记账。"""

    async def test_at_limit_rejects_and_does_not_record(self, monkeypatch) -> None:
        limit = int(tb.settings.daily_token_limit)
        state = _patch_usage(monkeypatch, limit, 0)
        allowed, info = await tb.check_and_record("c", "u-1", 100, 50)
        assert allowed is False
        assert info == {"used": limit, "limit": limit}
        assert state["recorded"] == []

    async def test_above_limit_rejects(self, monkeypatch) -> None:
        limit = int(tb.settings.daily_token_limit)
        state = _patch_usage(monkeypatch, limit + 1000, 0)
        allowed, info = await tb.check_and_record("b", "u-2", 0, 0)
        assert allowed is False
        assert info["used"] == limit + 1000
        assert state["recorded"] == []


class TestCheckAndRecordWarnBoundary:
    """80% 提醒边界矩阵。"""

    async def test_well_below_warn_no_flag(self, monkeypatch) -> None:
        limit = int(tb.settings.daily_token_limit)
        _patch_usage(monkeypatch, 0, 0)
        # 记一笔 100 → new_total/limit ≈ 0 < 0.8
        _, info = await tb.check_and_record("c", "u-1", 100, 0)
        assert info["warn"] is False

    async def test_exactly_at_warn_ratio_not_warn(self, monkeypatch) -> None:
        """new_total/limit > 0.8 才 warn；恰好 = 0.8 不触发（用 > 严格）。"""
        limit = int(tb.settings.daily_token_limit)
        # 让 new_total = limit * 0.8
        target = int(limit * 0.8)
        _patch_usage(monkeypatch, target, 0)
        _, info = await tb.check_and_record("c", "u-1", 0, 0)
        assert info["warn"] is False

    async def test_just_past_warn_triggers(self, monkeypatch) -> None:
        limit = int(tb.settings.daily_token_limit)
        target = int(limit * 0.8) + 1
        _patch_usage(monkeypatch, target, 0)
        _, info = await tb.check_and_record("c", "u-1", 0, 0)
        assert info["warn"] is True

    async def test_warn_close_to_full(self, monkeypatch) -> None:
        limit = int(tb.settings.daily_token_limit)
        _patch_usage(monkeypatch, limit - 100, 0)
        _, info = await tb.check_and_record("c", "u-1", 0, 0)
        # new_total = limit-100 < limit → 放行；ratio ≈ 99.98% > 80% → warn
        assert info["warn"] is True


class TestCheckAndRecordRecords:
    """放行路径必须落账，且参数透传正确。"""

    async def test_records_with_model(self, monkeypatch) -> None:
        state = _patch_usage(monkeypatch, 0, 0)
        allowed, info = await tb.check_and_record(
            "c", "u-9", 200, 50, model="claude-sonnet-4-6"
        )
        assert allowed is True
        assert info["used"] == 250
        assert info["limit"] == int(tb.settings.daily_token_limit)
        assert len(state["recorded"]) == 1
        r = state["recorded"][0]
        assert r["sid"] == "u-9"
        assert r["ut"] == "c"
        assert r["in"] == 200
        assert r["out"] == 50
        assert r["model"] == "claude-sonnet-4-6"

    async def test_records_with_default_model_none(self, monkeypatch) -> None:
        state = _patch_usage(monkeypatch, 0, 0)
        await tb.check_and_record("b", "u-3", 10, 10)
        assert state["recorded"][0]["model"] is None  # _record 内部再补"(unknown)"

    async def test_record_failure_propagates(self, monkeypatch) -> None:
        async def _gu(_s: str, _u: str, _d: str) -> tuple[int, int]:
            return 0, 0

        async def _rec(*_a: Any, **_k: Any) -> None:
            raise RuntimeError("write failed")

        monkeypatch.setattr(tb, "_get_used", _gu)
        monkeypatch.setattr(tb, "_record", _rec)
        with pytest.raises(RuntimeError, match="write failed"):
            await tb.check_and_record("c", "u-1", 100, 0)


class TestTodayDate:
    """_today 返回 UTC ISO 日期；快照断言依赖外部时钟，仅检查格式。"""

    def test_today_iso_format(self) -> None:
        s = tb._today()
        # YYYY-MM-DD
        assert len(s) == 10
        assert s[4] == "-" and s[7] == "-"
