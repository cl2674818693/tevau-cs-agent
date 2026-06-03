"""Tool: create_ticket（含人工接待 handoff 路径）

被测对象：tools.create_ticket.run
事项中心契约（docs/event-center-onboarding.md）：通过 event_center_client.create_task
推送，payload 字段为 event_id/action_type/source_module/event_type/context/priority/
entities/source_ref/callback_url。
- 参数校验：category / severity / user_type 枚举。
- 风暴对策：subject 24h 内已有未关闭工单 → 追加证据不新建。
- C/B entities：c → {type:customer, id}；b → {type:partner, id}。
- 推事项中心：create_task 返回 True → pushed_to_event_center=True；False → Lark 兜底。
- 人工介入工单：触发 _ensure_human_pending → 调 set_mode + broadcast。
"""

import pytest

from ai_engine.agent.tools import create_ticket as ct
from ai_engine.persistence.conversations import create_conversation, get_mode, set_mode
from ai_engine.persistence.tickets import find_open_ticket_for_subject


@pytest.fixture(autouse=True)
def _mock_outbound(monkeypatch):
    """拦截 create_task / Lark / 广播副作用，记录调用参数供断言。"""
    calls = {"create_task": [], "lark": [], "mode_change": []}

    async def _create_task(**kwargs):
        calls["create_task"].append(kwargs)
        return True

    async def _lark(payload):
        calls["lark"].append(payload)
        return None

    # patch 在 create_ticket 模块的引用名（from-import 后变成模块自己的属性）
    monkeypatch.setattr(ct, "create_task", _create_task)
    monkeypatch.setattr(ct, "_notify_lark", _lark)

    # broadcast 广播副作用拦截
    def _publish(_conv, _evt):
        calls["mode_change"].append((_conv, _evt))

    import ai_engine.api.staff_conversations as sc

    monkeypatch.setattr(sc, "publish_conversation_event", _publish)

    yield calls


class TestValidation:
    """枚举/类型校验，越界即抛 ValueError。"""

    async def test_invalid_category(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        with pytest.raises(ValueError, match="category"):
            await ct.run(
                subject_id="U001",
                user_type="c",
                conversation_id=conv,
                category="not-exist",
                summary="some summary here",
                severity="p2",
                evidence={"a": 1},
            )

    async def test_invalid_severity(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        with pytest.raises(ValueError, match="severity"):
            await ct.run(
                subject_id="U001",
                user_type="c",
                conversation_id=conv,
                category="bug",
                summary="some summary here",
                severity="p9",
                evidence={},
            )

    async def test_invalid_user_type(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        with pytest.raises(ValueError, match="user_type"):
            await ct.run(
                subject_id="U001",
                user_type="x",  # 非 c/b
                conversation_id=conv,
                category="bug",
                summary="ok summary text",
                severity="p2",
                evidence={},
            )


class TestSubjectEntities:
    """C 端 entities 含 type=customer；B 端 entities 含 type=partner。新契约用 entities 数组替代 user_id/bu_id 字段。"""

    async def test_c_customer_in_entities(self, _mock_outbound, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        out = await ct.run(
            subject_id="U001",
            user_type="c",
            conversation_id=conv,
            category="bug",
            summary="kyc failed report",
            severity="p2",
            evidence={"err": "x"},
        )
        assert out["external_ticket_id"].startswith("AI-")
        kw = _mock_outbound["create_task"][0]
        # 新契约：event_id 替代 external_ticket_id；entities 列表替代 user_id/bu_id
        assert kw["event_id"] == out["external_ticket_id"]
        assert kw["entities"][0] == {"type": "customer", "id": "U001"}

    async def test_b_partner_in_entities(self, _mock_outbound, seeded_db) -> None:
        conv = await create_conversation("b", "BU01")
        out = await ct.run(
            subject_id="BU01",
            user_type="b",
            conversation_id=conv,
            category="bug",
            summary="api 500 burst",
            severity="p1",
            evidence={"trace": "t"},
        )
        assert out["pushed_to_event_center"] is True
        kw = _mock_outbound["create_task"][0]
        assert kw["entities"][0] == {"type": "partner", "id": "BU01"}
        # severity p1 → priority 3（cs-engine p0 最高→事项中心 4 最高的反向映射）
        assert kw["priority"] == 3
        assert kw["action_type"] == "task"  # bug → task


class TestCategoryMapping:
    """category → action_type 映射：bug/事务/人工介入/CQ → task；无信息 → notify。"""

    async def test_no_info_maps_to_notify(self, _mock_outbound, seeded_db) -> None:
        conv = await create_conversation("c", "U002")
        await ct.run(
            subject_id="U002",
            user_type="c",
            conversation_id=conv,
            category="无信息",
            summary="not enough info to proceed",
            severity="p3",
            evidence={},
        )
        kw = _mock_outbound["create_task"][0]
        assert kw["action_type"] == "notify"
        assert kw["priority"] == 1  # p3 → 1（最低）


class TestEntityExtraction:
    """从 evidence 抽取 card_id / transaction_id 等关联实体。"""

    async def test_card_id_extracted(self, _mock_outbound, seeded_db) -> None:
        conv = await create_conversation("c", "U003")
        await ct.run(
            subject_id="U003",
            user_type="c",
            conversation_id=conv,
            category="bug",
            summary="card lock issue",
            severity="p2",
            evidence={"card_id": "CIDV012345"},
        )
        ents = _mock_outbound["create_task"][0]["entities"]
        assert {"type": "card", "id": "CIDV012345"} in ents

    async def test_transaction_extracted_camelcase(self, _mock_outbound, seeded_db) -> None:
        # AI 可能用 camelCase 或 snake_case，两种命名都要识别
        conv = await create_conversation("c", "U004")
        await ct.run(
            subject_id="U004",
            user_type="c",
            conversation_id=conv,
            category="bug",
            summary="txn missing",
            severity="p2",
            evidence={"orderId": "ORDER_001"},
        )
        ents = _mock_outbound["create_task"][0]["entities"]
        assert {"type": "transaction", "id": "ORDER_001"} in ents


class TestStormDedupe:
    """同 subject 24h 内未关闭工单 → 追加证据不新建。"""

    async def test_duplicate_appends_evidence(self, _mock_outbound, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        first = await ct.run(
            subject_id="U001",
            user_type="c",
            conversation_id=conv,
            category="bug",
            summary="first ticket summary",
            severity="p2",
            evidence={"a": 1},
        )
        second = await ct.run(
            subject_id="U001",
            user_type="c",
            conversation_id=conv,
            category="bug",
            summary="second ticket same issue",
            severity="p2",
            evidence={"b": 2},
        )
        assert second["external_ticket_id"] == first["external_ticket_id"]
        assert second["appended_to_existing"] is True
        # 第 2 次不重复 POST（复用现有 ticket）
        assert len(_mock_outbound["create_task"]) == 1


class TestPushFailureTriggersLark:
    """推事项中心失败 → 走 Lark 兜底；返回 pushed_to_event_center=False。"""

    async def test_create_task_returns_false_triggers_lark(
        self, _mock_outbound, monkeypatch, seeded_db
    ) -> None:
        """create_task 返回 False（HTTP 非 2xx 或异常时由 client 内部捕获）→ 走 Lark 兜底。"""
        async def _fail(**_kwargs):
            return False

        monkeypatch.setattr(ct, "create_task", _fail)
        conv = await create_conversation("c", "U001")
        out = await ct.run(
            subject_id="U001",
            user_type="c",
            conversation_id=conv,
            category="bug",
            summary="downstream is unhappy",
            severity="p2",
            evidence={},
        )
        assert out["pushed_to_event_center"] is False
        assert len(_mock_outbound["lark"]) == 1
        assert "兜底" in _mock_outbound["lark"][0]["text"]


class TestHumanHandoff:
    """人工介入类工单：会话 mode=ai → 切到 human_pending + 广播 mode_change。"""

    async def test_human_intervention_switches_mode(
        self, _mock_outbound, seeded_db
    ) -> None:
        conv = await create_conversation("c", "U001")
        await ct.run(
            subject_id="U001",
            user_type="c",
            conversation_id=conv,
            category="人工介入",
            summary="please help",
            severity="p2",
            evidence={},
        )
        mode, _ = await get_mode(conv)
        assert mode == "human_pending"
        # 广播了 mode_change
        assert _mock_outbound["mode_change"] and (
            _mock_outbound["mode_change"][0][1]["type"] == "mode_change"
        )

    async def test_human_intervention_skipped_when_already_human(
        self, _mock_outbound, seeded_db
    ) -> None:
        """会话已经在 human_takeover 时不再重切 mode（避免抖动）。"""
        conv = await create_conversation("c", "U001")
        await set_mode(conv, "human_takeover", "staff1")
        before = list(_mock_outbound["mode_change"])
        await ct.run(
            subject_id="U001",
            user_type="c",
            conversation_id=conv,
            category="人工介入",
            summary="dup human ask",
            severity="p2",
            evidence={},
        )
        mode, sid = await get_mode(conv)
        assert mode == "human_takeover"
        assert sid == "staff1"
        # 不应该有新的 mode_change 广播
        assert _mock_outbound["mode_change"] == before

    async def test_non_human_category_does_not_switch_mode(
        self, _mock_outbound, seeded_db
    ) -> None:
        conv = await create_conversation("c", "U001")
        await ct.run(
            subject_id="U001",
            user_type="c",
            conversation_id=conv,
            category="bug",  # 非"人工介入"
            summary="normal bug ticket",
            severity="p2",
            evidence={},
        )
        mode, _ = await get_mode(conv)
        assert mode == "ai"
        assert _mock_outbound["mode_change"] == []


class TestFindOpenTicketSurfacedByDAO:
    async def test_dao_finds_open_ticket(self, _mock_outbound, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        out = await ct.run(
            subject_id="U001",
            user_type="c",
            conversation_id=conv,
            category="bug",
            summary="discoverable summary",
            severity="p2",
            evidence={},
        )
        ext = await find_open_ticket_for_subject("U001", "c")
        assert ext == out["external_ticket_id"]
