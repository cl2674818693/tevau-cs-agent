"""Unit tests: governance.rate_limit

被测对象：单 subject 每分钟消息数滑动窗口（spec §6.4 兜底层）。
mock 策略：
- 进程内窗口直接测 _local_check / reset。
- check() 走两条分支：无 redis（fail-through 到 local）/ redis 故障（fail-open 回落 local）。
- 不打真实 redis；mock `_get_redis()` 返回 None 或一个抛错的伪客户端。
- 时间相关测试用 monkeypatch 替换 `time.monotonic`，避免 sleep 拖慢。
"""

from typing import Any

import pytest

from ai_engine.governance import rate_limit as rl


@pytest.fixture(autouse=True)
def _reset_local() -> None:
    """每个 case 跑前清空进程内窗口，避免相互污染。"""
    rl.reset()
    yield
    rl.reset()


@pytest.fixture
def fake_clock(monkeypatch):
    """伪造 time.monotonic：测试可显式推进 now，验证窗口滑动。"""
    state = {"now": 1000.0}

    def _now() -> float:
        return state["now"]

    monkeypatch.setattr(rl.time, "monotonic", _now)
    return state


class TestLocalCheckBoundary:
    """_local_check 单窗口阈值矩阵：limit-1 / limit / limit+1。"""

    def test_allows_first_hit(self, fake_clock) -> None:
        allowed, retry = rl._local_check("k", limit=3)
        assert allowed is True
        assert retry == 0

    def test_allows_until_limit_minus_one(self, fake_clock) -> None:
        # limit=3：前 3 次全放行（第 3 次是恰好 = limit-0 之前的最后一次）
        for _ in range(3):
            allowed, _ = rl._local_check("k", limit=3)
            assert allowed is True

    def test_rejects_at_limit(self, fake_clock) -> None:
        for _ in range(3):
            rl._local_check("k", limit=3)
        allowed, retry = rl._local_check("k", limit=3)  # 第 4 次：dq 已满 3
        assert allowed is False
        # 同一 now：retry = window - 0 = 60000 ms
        assert retry == 60_000

    def test_rejects_above_limit(self, fake_clock) -> None:
        for _ in range(10):
            rl._local_check("k", limit=3)
        allowed, _ = rl._local_check("k", limit=3)
        assert allowed is False

    def test_limit_zero_always_rejects(self, fake_clock) -> None:
        """limit=0 边界：直接拒绝且 retry=0（不进入 dq 索引分支，避免 IndexError）。"""
        assert rl._local_check("k", limit=0) == (False, 0)
        # 多次调用同样幂等拒绝
        assert rl._local_check("k", limit=0) == (False, 0)

    def test_limit_one_first_allow_then_reject(self, fake_clock) -> None:
        a1, _ = rl._local_check("k", limit=1)
        a2, _ = rl._local_check("k", limit=1)
        assert a1 is True
        assert a2 is False


class TestLocalCheckWindowSliding:
    """窗口滑动：超过 60s 旧记录应被清掉，重新放行。"""

    def test_old_entries_evicted_after_window(self, fake_clock) -> None:
        rl._local_check("k", limit=2)
        rl._local_check("k", limit=2)
        # 推进时间到窗口外
        fake_clock["now"] += 60.0  # 严格 >= window
        allowed, _ = rl._local_check("k", limit=2)
        assert allowed is True

    def test_entries_within_window_not_evicted(self, fake_clock) -> None:
        rl._local_check("k", limit=2)
        rl._local_check("k", limit=2)
        fake_clock["now"] += 30.0  # 仍在窗口内
        allowed, _ = rl._local_check("k", limit=2)
        assert allowed is False

    def test_retry_after_decreases_as_time_passes(self, fake_clock) -> None:
        rl._local_check("k", limit=1)
        # 此刻拒绝：retry = 60000
        _, r0 = rl._local_check("k", limit=1)
        assert r0 == 60_000
        # 推进 25s 再问
        fake_clock["now"] += 25.0
        _, r1 = rl._local_check("k", limit=1)
        assert r1 == 35_000  # 60000 - 25000

    def test_retry_clamped_to_zero(self, fake_clock, monkeypatch) -> None:
        """理论上 retry 为负应被 clamp 到 0（max(retry, 0)）。"""
        # 让窗口刚好踩到边界：dq[0]=1000.0, now=1060.001 → retry 应 < 0
        rl._local_check("k", limit=1)
        fake_clock["now"] = 1060.001
        # window 内还差一点点 ≥ 60s（_local_check 用 >= 判断弹出）
        allowed, retry = rl._local_check("k", limit=1)
        # 极小负值被 clamp（也可能 popleft 后放行）；任一都不应是负数
        assert retry >= 0
        assert isinstance(allowed, bool)


class TestReset:
    def test_reset_clears_all_keys(self, fake_clock) -> None:
        rl._local_check("a", limit=1)
        rl._local_check("b", limit=1)
        # 在 reset 前两个 key 都已用满
        assert rl._local_check("a", limit=1)[0] is False
        assert rl._local_check("b", limit=1)[0] is False
        rl.reset()
        assert rl._local_check("a", limit=1)[0] is True
        assert rl._local_check("b", limit=1)[0] is True


class TestCheckAsyncFallback:
    """check() 入口：无 redis / redis 故障两条分支。"""

    async def test_no_redis_uses_local(self, monkeypatch, fake_clock) -> None:
        """settings.redis_url 为 None → _get_redis 返回 None → 走 _local_check。"""
        monkeypatch.setattr(rl, "_get_redis", lambda: None)
        # limit 取 settings.chat_rate_limit_per_min（默认 30）
        for _ in range(int(rl.settings.chat_rate_limit_per_min)):
            allowed, _ = await rl.check("subj-1")
            assert allowed is True
        # 第 31 次应拒
        allowed, retry = await rl.check("subj-1")
        assert allowed is False
        assert retry > 0

    async def test_redis_failure_fail_open_to_local(
        self, monkeypatch, fake_clock, caplog
    ) -> None:
        """redis.eval 抛错时：告警 + 回退本地窗口，仍然放行（fail-open）。"""

        class _BoomRedis:
            async def eval(self, *_a: Any, **_k: Any) -> Any:
                raise RuntimeError("redis down")

        monkeypatch.setattr(rl, "_get_redis", lambda: _BoomRedis())
        import logging

        with caplog.at_level(logging.WARNING, logger=rl.logger.name):
            allowed, retry = await rl.check("subj-1")
        assert allowed is True
        assert retry == 0
        # 应记一条 warning（含异常）
        assert any("redis unavailable" in rec.getMessage() for rec in caplog.records)

    async def test_redis_normal_path_allowed(self, monkeypatch) -> None:
        """模拟 redis.eval 返回 [1, 0] → 放行；不接触本地窗口。"""

        class _OkRedis:
            async def eval(self, *_a: Any, **_k: Any) -> list[int]:
                return [1, 0]

        monkeypatch.setattr(rl, "_get_redis", lambda: _OkRedis())
        allowed, retry = await rl.check("subj-1")
        assert allowed is True
        assert retry == 0

    async def test_redis_normal_path_rejected(self, monkeypatch) -> None:
        """redis.eval 返回 [0, 5000] → 拒绝 + retry=5000。"""

        class _DenyRedis:
            async def eval(self, *_a: Any, **_k: Any) -> list[int]:
                return [0, 5000]

        monkeypatch.setattr(rl, "_get_redis", lambda: _DenyRedis())
        allowed, retry = await rl.check("subj-1")
        assert allowed is False
        assert retry == 5000

    async def test_redis_eval_returns_strings_coerced(self, monkeypatch) -> None:
        """redis 客户端 decode_responses 后可能返回 str；check 用 int() 强转，应可正常解析。"""

        class _StrRedis:
            async def eval(self, *_a: Any, **_k: Any) -> list[str]:
                return ["1", "0"]

        monkeypatch.setattr(rl, "_get_redis", lambda: _StrRedis())
        allowed, retry = await rl.check("subj-1")
        assert allowed is True
        assert retry == 0


class TestKeyIsolation:
    """不同 key 各自独立计数。"""

    def test_keys_are_independent(self, fake_clock) -> None:
        rl._local_check("k1", limit=1)
        # k1 满了，k2 仍可
        assert rl._local_check("k1", limit=1)[0] is False
        assert rl._local_check("k2", limit=1)[0] is True
