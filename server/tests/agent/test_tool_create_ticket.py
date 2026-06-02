"""Tool: create_ticket（含人工接待 handoff 路径）

被测对象：tools.create_ticket.run
- 参数校验：category / severity / user_type 枚举。
- 风暴对策：subject 24h 内已有未关闭工单 → 追加证据不新建。
- C/B subject_key：c → user_id；b → bu_id。
- 推事项中心：HTTP 2xx → pushed_to_event_center=True；否则 Lark 兜底。
- 人工介入工单：触发 _ensure_human_pending → 调 set_mode + broadcast。
"""

import pytest

from ai_engine.agent.tools import create_ticket as ct
from ai_engine.persistence.conversations import create_conversation, get_mode, set_mode
from ai_engine.persistence.tickets import find_open_ticket_for_subject


class _FakeResp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


@pytest.fixture(autouse=True)
def _mock_outbound(monkeypatch):
    """统一拦截 HTTP/Lark/广播副作用，避免真正走网络。"""
    calls = {"post": [], "lark": [], "mode_change": []}

    async def _post(url, json, headers):  # noqa: ANN001,ARG001
        calls["post"].append({"url": url, "json": json, "headers": headers})
        return _FakeResp(200)

    async def _lark(payload):
        calls["lark"].append(payload)
        return None

    monkeypatch.setattr(ct, "_post", _post)
    monkeypatch.setattr(ct, "_notify_lark", _lark)

    # broadcast 广播副作用拦截
    def _publish(_conv, _evt):
        calls["mode_change"].append((_conv, _evt))

    import ai_engine.api.staff_conversations as sc

    monkeypatch.setattr(sc, "publish_conversation_event", _publish)

    # 不再 monkeypatch settings.event_center_*：_post 已 mock，url 取真实值无网络发起；
    # _sign 用 .env 的 EVENT_CENTER_SECRET_CURRENT，非空即可（直接 monkeypatch _SettingsProxy
    # 会导致进程级状态泄漏到后续测试模块）。
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


class TestSubjectKey:
    """C 端工单填 user_id；B 端填 bu_id。"""

    async def test_c_user_id_in_payload(self, _mock_outbound, seeded_db) -> None:
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
        body = _mock_outbound["post"][0]["json"]
        assert body["user_id"] == "U001"
        assert "bu_id" not in body

    async def test_b_bu_id_in_payload(self, _mock_outbound, seeded_db) -> None:
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
        body = _mock_outbound["post"][0]["json"]
        assert body["bu_id"] == "BU01"
        assert "user_id" not in body


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
        # 第 2 次不重复 POST
        assert len(_mock_outbound["post"]) == 1


class TestPushFailureTriggersLark:
    """推事项中心失败 → 走 Lark 兜底；返回 pushed_to_event_center=False。"""

    async def test_non_2xx_triggers_lark(self, _mock_outbound, monkeypatch, seeded_db) -> None:
        async def _post500(url, json, headers):  # noqa: ANN001,ARG001
            return _FakeResp(500)

        monkeypatch.setattr(ct, "_post", _post500)
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

    async def test_http_exception_triggers_lark(
        self, _mock_outbound, monkeypatch, seeded_db
    ) -> None:
        async def _boom(*_a, **_k):  # noqa: ANN002,ANN003
            raise RuntimeError("connreset")

        monkeypatch.setattr(ct, "_post", _boom)
        conv = await create_conversation("c", "U001")
        out = await ct.run(
            subject_id="U001",
            user_type="c",
            conversation_id=conv,
            category="bug",
            summary="net down on send",
            severity="p1",
            evidence={},
        )
        assert out["pushed_to_event_center"] is False
        assert len(_mock_outbound["lark"]) == 1


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
