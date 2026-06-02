"""Persistence: admin_sla.py — SLA 策略 CRUD + 违规即时计算。

覆盖：create_policy（metric 校验）/ list_policies / set_policy_active /
delete_policy / compute_breaches（take_time / resolve_time, 阈值边界,
archived 排除, 已 end 的不算）。
"""

from datetime import UTC, datetime, timedelta

import pytest

from ai_engine.persistence import (
    admin_sla,
    conversations as conv,
    staff_metrics as sm,
)
from ai_engine.persistence.db import execute, init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestCreatePolicy:
    @pytest.mark.parametrize("metric", ["take_time", "resolve_time"])
    async def test_valid_metric(self, db_ready, metric: str) -> None:
        pid = await admin_sla.create_policy(metric, 60, "all", None)
        assert pid > 0

    async def test_invalid_metric_raises(self, db_ready) -> None:
        with pytest.raises(ValueError):
            await admin_sla.create_policy("response_time", 60, "all", None)

    async def test_scope_user_type(self, db_ready) -> None:
        pid = await admin_sla.create_policy("take_time", 30, "user_type", "c")
        rows = await admin_sla.list_policies()
        assert rows[0]["id"] == pid
        assert rows[0]["scope"] == "user_type"
        assert rows[0]["scope_value"] == "c"


class TestListAndMutate:
    async def test_list_ordered(self, db_ready) -> None:
        a = await admin_sla.create_policy("take_time", 30, "all", None)
        b = await admin_sla.create_policy("resolve_time", 600, "all", None)
        rows = await admin_sla.list_policies()
        assert [r["id"] for r in rows] == [a, b]

    async def test_set_active(self, db_ready) -> None:
        pid = await admin_sla.create_policy("take_time", 30, "all", None)
        await admin_sla.set_policy_active(pid, 0)
        rows = await admin_sla.list_policies()
        assert rows[0]["active"] == 0

    async def test_delete(self, db_ready) -> None:
        pid = await admin_sla.create_policy("take_time", 30, "all", None)
        await admin_sla.delete_policy(pid)
        assert await admin_sla.list_policies() == []

    async def test_delete_missing_no_error(self, db_ready) -> None:
        await admin_sla.delete_policy(99999)


class TestComputeBreaches:
    async def test_no_policies_no_breaches(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        assert await admin_sla.compute_breaches() == []

    async def test_take_time_breach(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        # 把 created_at 改成 600s 前
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid}
        )
        await admin_sla.create_policy("take_time", 60, "all", None)
        breaches = await admin_sla.compute_breaches()
        assert len(breaches) == 1
        assert breaches[0]["conversation_id"] == cid
        assert breaches[0]["metric"] == "take_time"
        assert breaches[0]["threshold_seconds"] == 60
        assert breaches[0]["elapsed_seconds"] >= 60

    async def test_take_time_not_breached_under_threshold(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        await admin_sla.create_policy("take_time", 3600, "all", None)
        assert await admin_sla.compute_breaches() == []

    async def test_already_taken_excluded_from_take_breach(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid}
        )
        await sm.log_staff_action(cid, "s1", "take")
        await admin_sla.create_policy("take_time", 60, "all", None)
        # 已 take → take_time 不算违规
        breaches = [b for b in await admin_sla.compute_breaches() if b["metric"] == "take_time"]
        assert breaches == []

    async def test_resolve_time_breach(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_takeover", assigned_staff_id="s1")
        await sm.log_staff_action(cid, "s1", "take")
        # 把 take 时间倒推
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute("UPDATE staff_actions SET at=:t WHERE conversation_id=:c", {"t": old, "c": cid})
        await admin_sla.create_policy("resolve_time", 60, "all", None)
        breaches = await admin_sla.compute_breaches()
        assert any(b["metric"] == "resolve_time" and b["conversation_id"] == cid for b in breaches)

    async def test_resolved_excludes_from_resolve_breach(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_takeover", assigned_staff_id="s1")
        await sm.log_staff_action(cid, "s1", "take")
        await sm.log_staff_action(cid, "s1", "resolved")
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute("UPDATE staff_actions SET at=:t", {"t": old})
        await admin_sla.create_policy("resolve_time", 60, "all", None)
        breaches = [b for b in await admin_sla.compute_breaches() if b["metric"] == "resolve_time"]
        assert breaches == []

    async def test_archived_excluded(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid}
        )
        await conv.archive_conversation(cid)
        await admin_sla.create_policy("take_time", 60, "all", None)
        assert await admin_sla.compute_breaches() == []

    async def test_inactive_policy_not_applied(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid}
        )
        pid = await admin_sla.create_policy("take_time", 60, "all", None)
        await admin_sla.set_policy_active(pid, 0)
        assert await admin_sla.compute_breaches() == []

    async def test_min_threshold_wins(self, db_ready) -> None:
        """同一 metric 多条 active → 取最小阈值（严格策略）。"""
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        old = (datetime.now(UTC) - timedelta(seconds=120)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid}
        )
        await admin_sla.create_policy("take_time", 60, "all", None)
        await admin_sla.create_policy("take_time", 300, "all", None)
        breaches = await admin_sla.compute_breaches()
        # 60s 阈值生效（120>60）；300 阈值不会让该会话脱敏，因为 min 是 60
        assert breaches[0]["threshold_seconds"] == 60
