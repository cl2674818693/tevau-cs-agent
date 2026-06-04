"""Persistence: tickets.py — 工单与事件 CRUD / 状态映射 / 镜像查询。

覆盖：create_ticket / append_ticket_event / find_open_ticket_for_subject /
update_ticket_severity / list_tickets(open_only/severity/category/before_id) /
get_ticket（含事件聚合）。

工单状态由"最新一条事件"映射（_STATUS_OF_EVENT）。
"""

import asyncio

import pytest

from ai_engine.persistence import conversations as conv
from ai_engine.persistence import tickets
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


@pytest.fixture
async def conv_id(db_ready):
    return await conv.create_conversation("c", "U1")


class TestCreateTicket:
    async def test_create_basic(self, db_ready, conv_id) -> None:
        payload = {"category": "card_lock", "severity": "P2", "user_id": "U1", "user_type": "c"}
        await tickets.create_ticket("T-001", conv_id, payload)
        row = await tickets.get_ticket("T-001")
        assert row is not None
        assert row["external_id"] == "T-001"
        assert row["conversation_id"] == conv_id
        assert row["current_severity"] == "P2"

    async def test_severity_omitted_stays_null(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-002", conv_id, {"category": "x"})
        row = await tickets.get_ticket("T-002")
        assert row is not None and row["current_severity"] is None

    async def test_duplicate_external_id_raises(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-003", conv_id, {"category": "x"})
        with pytest.raises(Exception):  # noqa: B017 唯一主键违例
            await tickets.create_ticket("T-003", conv_id, {"category": "y"})


class TestAppendTicketEvent:
    async def test_append_basic(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        await tickets.append_ticket_event("T-1", "in_progress", "ops-1", "处理中", {"k": 1})
        row = await tickets.get_ticket("T-1")
        assert row is not None
        assert len(row["events"]) == 1
        assert row["events"][0]["event"] == "in_progress"
        assert row["events"][0]["actor"] == "ops-1"
        assert row["events"][0]["comment"] == "处理中"

    async def test_event_order_preserved(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        for ev in ("in_progress", "resolved", "closed"):
            await tickets.append_ticket_event("T-1", ev, None, None, None)
        row = await tickets.get_ticket("T-1")
        assert [e["event"] for e in row["events"]] == ["in_progress", "resolved", "closed"]


class TestFindOpenTicketForSubject:
    async def test_returns_unclosed_match(self, db_ready, conv_id) -> None:
        await tickets.create_ticket(
            "T-1", conv_id, {"user_id": "U1", "user_type": "c", "category": "x"}
        )
        eid = await tickets.find_open_ticket_for_subject("U1", "c")
        assert eid == "T-1"

    async def test_closed_returns_none(self, db_ready, conv_id) -> None:
        await tickets.create_ticket(
            "T-1", conv_id, {"user_id": "U1", "user_type": "c"}
        )
        await tickets.append_ticket_event("T-1", "closed", None, None, None)
        assert await tickets.find_open_ticket_for_subject("U1", "c") is None

    async def test_wrong_subject_returns_none(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {"user_id": "U1", "user_type": "c"})
        assert await tickets.find_open_ticket_for_subject("U2", "c") is None

    async def test_wrong_user_type_returns_none(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {"user_id": "U1", "user_type": "c"})
        # b 端按 bu_id 找
        assert await tickets.find_open_ticket_for_subject("U1", "b") is None

    async def test_b_uses_bu_id_key(self, db_ready, conv_id) -> None:
        await tickets.create_ticket(
            "T-1", conv_id, {"bu_id": "BU1", "user_type": "b"}
        )
        assert await tickets.find_open_ticket_for_subject("BU1", "b") == "T-1"

    async def test_outside_window_returns_none(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {"user_id": "U1", "user_type": "c"})
        # within_hours=0 → cutoff≈now；created_at 是秒级时间戳，需跨过 1 秒才严格在窗外
        await asyncio.sleep(1.05)
        assert await tickets.find_open_ticket_for_subject("U1", "c", within_hours=0) is None


class TestUpdateTicketSeverity:
    async def test_overwrite(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {"severity": "P3"})
        await tickets.update_ticket_severity("T-1", "P1")
        row = await tickets.get_ticket("T-1")
        assert row is not None and row["current_severity"] == "P1"

    async def test_nonexistent_no_error(self, db_ready) -> None:
        await tickets.update_ticket_severity("nope", "P1")  # 不抛错


class TestListTickets:
    async def test_default_lists_all_newest_first(self, db_ready, conv_id) -> None:
        # 默认排序 ORDER BY created_at DESC, external_id DESC：created_at 秒级一致时
        # external_id DESC 也会让 T-2 在前，所以无需跨秒等待。
        for i in range(3):
            await tickets.create_ticket(f"T-{i}", conv_id, {"category": "x"})
        rows = await tickets.list_tickets()
        assert [r["external_id"] for r in rows] == ["T-2", "T-1", "T-0"]

    async def test_open_only_excludes_closed(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-open", conv_id, {})
        await tickets.create_ticket("T-closed", conv_id, {})
        await tickets.append_ticket_event("T-closed", "closed", None, None, None)
        rows = await tickets.list_tickets(open_only=True)
        ids = {r["external_id"] for r in rows}
        assert "T-open" in ids and "T-closed" not in ids

    async def test_filter_by_severity(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-P1", conv_id, {"severity": "P1"})
        await tickets.create_ticket("T-P3", conv_id, {"severity": "P3"})
        rows = await tickets.list_tickets(severity="P1")
        assert [r["external_id"] for r in rows] == ["T-P1"]

    async def test_filter_by_category(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-A", conv_id, {"category": "card_lock"})
        await tickets.create_ticket("T-B", conv_id, {"category": "kyc"})
        rows = await tickets.list_tickets(category="kyc")
        assert [r["external_id"] for r in rows] == ["T-B"]

    async def test_limit_respected(self, db_ready, conv_id) -> None:
        for i in range(5):
            await tickets.create_ticket(f"T-{i}", conv_id, {})
            await asyncio.sleep(0.01)
        rows = await tickets.list_tickets(limit=2)
        assert len(rows) == 2

    async def test_status_pending_when_no_events(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        rows = await tickets.list_tickets()
        assert rows[0]["status"] == "pending"
        assert rows[0]["closed"] is False

    async def test_status_in_progress_after_event(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        await tickets.append_ticket_event("T-1", "in_progress", None, None, None)
        rows = await tickets.list_tickets()
        assert rows[0]["status"] == "in_progress"

    async def test_status_resolved_mapping(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        await tickets.append_ticket_event("T-1", "resolved", None, None, None)
        rows = await tickets.list_tickets()
        assert rows[0]["status"] == "resolved"

    async def test_status_user_confirmed_resolved_maps_to_resolved(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        await tickets.append_ticket_event("T-1", "user_confirmed_resolved", None, None, None)
        rows = await tickets.list_tickets()
        assert rows[0]["status"] == "resolved"

    async def test_status_user_rejected_maps_to_in_progress(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        await tickets.append_ticket_event("T-1", "resolved", None, None, None)
        await tickets.append_ticket_event("T-1", "user_rejected_resolved", None, None, None)
        rows = await tickets.list_tickets()
        # 最新事件是 user_rejected_resolved → in_progress
        assert rows[0]["status"] == "in_progress"

    async def test_unknown_event_falls_back_to_in_progress(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        await tickets.append_ticket_event("T-1", "bogus_event", None, None, None)
        rows = await tickets.list_tickets()
        assert rows[0]["status"] == "in_progress"

    async def test_closed_flag_when_closed(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        await tickets.append_ticket_event("T-1", "closed", None, None, None)
        rows = await tickets.list_tickets()
        assert rows[0]["closed"] is True
        assert rows[0]["status"] == "closed"

    async def test_filter_by_status_pending(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-pending", conv_id, {})
        await tickets.create_ticket("T-prog", conv_id, {})
        await tickets.append_ticket_event("T-prog", "in_progress", None, None, None)
        rows = await tickets.list_tickets(status="pending")
        assert [r["external_id"] for r in rows] == ["T-pending"]

    async def test_filter_by_status_in_progress(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-pending", conv_id, {})
        await tickets.create_ticket("T-prog", conv_id, {})
        await tickets.create_ticket("T-resolved", conv_id, {})
        await tickets.create_ticket("T-closed", conv_id, {})
        await tickets.append_ticket_event("T-prog", "in_progress", None, None, None)
        await tickets.append_ticket_event("T-resolved", "resolved", None, None, None)
        await tickets.append_ticket_event("T-closed", "closed", None, None, None)
        rows = await tickets.list_tickets(status="in_progress")
        ids = {r["external_id"] for r in rows}
        assert ids == {"T-prog"}

    async def test_filter_status_in_progress_includes_user_rejected(
        self, db_ready, conv_id
    ) -> None:
        await tickets.create_ticket("T-rej", conv_id, {})
        await tickets.append_ticket_event("T-rej", "resolved", None, None, None)
        await tickets.append_ticket_event("T-rej", "user_rejected_resolved", None, None, None)
        rows = await tickets.list_tickets(status="in_progress")
        assert {r["external_id"] for r in rows} == {"T-rej"}

    async def test_filter_status_in_progress_includes_unknown_event(
        self, db_ready, conv_id
    ) -> None:
        # 与 _STATUS_OF_EVENT 的兜底一致：未知事件归 in_progress
        await tickets.create_ticket("T-bogus", conv_id, {})
        await tickets.append_ticket_event("T-bogus", "bogus_event", None, None, None)
        rows = await tickets.list_tickets(status="in_progress")
        assert {r["external_id"] for r in rows} == {"T-bogus"}

    async def test_filter_by_status_resolved(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-r1", conv_id, {})
        await tickets.create_ticket("T-r2", conv_id, {})
        await tickets.create_ticket("T-prog", conv_id, {})
        await tickets.append_ticket_event("T-r1", "resolved", None, None, None)
        await tickets.append_ticket_event("T-r2", "user_confirmed_resolved", None, None, None)
        await tickets.append_ticket_event("T-prog", "in_progress", None, None, None)
        rows = await tickets.list_tickets(status="resolved")
        ids = {r["external_id"] for r in rows}
        assert ids == {"T-r1", "T-r2"}

    async def test_filter_by_status_closed(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-c", conv_id, {})
        await tickets.create_ticket("T-r", conv_id, {})
        await tickets.append_ticket_event("T-c", "closed", None, None, None)
        await tickets.append_ticket_event("T-r", "resolved", None, None, None)
        rows = await tickets.list_tickets(status="closed")
        assert {r["external_id"] for r in rows} == {"T-c"}

    async def test_filter_status_resolved_then_closed_is_closed(
        self, db_ready, conv_id
    ) -> None:
        # 同时存在 resolved + closed 事件：最新是 closed，应只在 status=closed 命中
        await tickets.create_ticket("T-rc", conv_id, {})
        await tickets.append_ticket_event("T-rc", "resolved", None, None, None)
        await tickets.append_ticket_event("T-rc", "closed", None, None, None)
        resolved_rows = await tickets.list_tickets(status="resolved")
        closed_rows = await tickets.list_tickets(status="closed")
        assert all(r["external_id"] != "T-rc" for r in resolved_rows)
        assert {r["external_id"] for r in closed_rows} == {"T-rc"}

    async def test_filter_unknown_status_returns_empty(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        rows = await tickets.list_tickets(status="bogus")
        assert rows == []

    async def test_status_filter_combines_with_severity(
        self, db_ready, conv_id
    ) -> None:
        await tickets.create_ticket("T-1", conv_id, {"severity": "P1"})
        await tickets.create_ticket("T-2", conv_id, {"severity": "P2"})
        await tickets.append_ticket_event("T-1", "in_progress", None, None, None)
        await tickets.append_ticket_event("T-2", "in_progress", None, None, None)
        rows = await tickets.list_tickets(status="in_progress", severity="P1")
        assert {r["external_id"] for r in rows} == {"T-1"}

    async def test_before_id_cursor(self, db_ready, conv_id) -> None:
        # created_at 是秒级时间戳，需跨秒才能让 t.created_at < :cur_at 严格成立
        await tickets.create_ticket("T-0", conv_id, {})
        await asyncio.sleep(1.05)
        await tickets.create_ticket("T-1", conv_id, {})
        await asyncio.sleep(1.05)
        await tickets.create_ticket("T-2", conv_id, {})
        rows = await tickets.list_tickets(before_id="T-2")
        out_ids = [r["external_id"] for r in rows]
        assert out_ids == ["T-1", "T-0"]

    async def test_before_id_invalid_returns_all(self, db_ready, conv_id) -> None:
        """游标查不到 → 不加 WHERE，返回全部。"""
        await tickets.create_ticket("T-1", conv_id, {})
        rows = await tickets.list_tickets(before_id="nope")
        assert len(rows) == 1


class TestGetTicket:
    async def test_returns_none_when_missing(self, db_ready) -> None:
        assert await tickets.get_ticket("missing") is None

    async def test_events_attached_in_order(self, db_ready, conv_id) -> None:
        await tickets.create_ticket("T-1", conv_id, {})
        await tickets.append_ticket_event("T-1", "in_progress", "a1", None, None)
        await tickets.append_ticket_event("T-1", "resolved", "a2", "ok", None)
        row = await tickets.get_ticket("T-1")
        assert row is not None
        assert [e["event"] for e in row["events"]] == ["in_progress", "resolved"]
