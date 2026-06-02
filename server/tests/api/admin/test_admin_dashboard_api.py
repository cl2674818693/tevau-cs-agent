"""管理后台首页大盘 /admin/api/v1/dashboard/overview。

被测：admin_dashboard.overview → 复用 staff_metrics.ai_quality 聚合。
覆盖：rbac（agent 403 / 未带 token 401 / supervisor|manager|admin 全部 2xx）、
     空数据健壮性、时间窗 from/to 过滤、聚合数字与底层 DAO 同步。
"""

from typing import ClassVar

import pytest


@pytest.mark.usefixtures("init_self_db")
class TestDashboardOverviewAuth:
    """鉴权矩阵：admin/supervisor/manager 通过；agent/senior/engineer 403；缺 token 401。"""

    async def test_no_token_returns_401(self, client) -> None:
        r = await client.get("/admin/api/v1/dashboard/overview")
        assert r.status_code == 401

    async def test_malformed_bearer_returns_401(self, client) -> None:
        r = await client.get(
            "/admin/api/v1/dashboard/overview",
            headers={"Authorization": "Token notbearer"},
        )
        assert r.status_code == 401

    async def test_invalid_signature_returns_401(self, client) -> None:
        r = await client.get(
            "/admin/api/v1/dashboard/overview",
            headers={"Authorization": "Bearer bogus.jwt.value"},
        )
        assert r.status_code == 401

    @pytest.mark.parametrize("role", ["admin", "supervisor", "manager"])
    async def test_view_roles_pass(self, client, auth_headers, role: str) -> None:
        r = await client.get(
            "/admin/api/v1/dashboard/overview", headers=auth_headers(role)
        )
        assert r.status_code == 200

    @pytest.mark.parametrize("role", ["agent", "senior", "engineer"])
    async def test_non_view_roles_forbidden(self, client, auth_headers, role: str) -> None:
        r = await client.get(
            "/admin/api/v1/dashboard/overview", headers=auth_headers(role)
        )
        assert r.status_code == 403


@pytest.mark.usefixtures("init_self_db")
class TestDashboardOverviewShape:
    """返回字段齐全：包含转人工/差评/工具/超范围/失败回合等全部 KPI 键。"""

    _EXPECTED_KEYS: ClassVar[set[str]] = {
        "total_conversations",
        "handoff",
        "handoff_rate",
        "upvote",
        "downvote",
        "downvote_rate",
        "tool_calls",
        "tool_empty",
        "tool_empty_rate",
        "out_of_scope",
        "failed_turns",
    }

    async def test_empty_db_returns_zero_metrics(self, client, admin_headers) -> None:
        """无任何数据时不应抛错；各计数为 0，比率为 0.0（防除零）。"""
        r = await client.get("/admin/api/v1/dashboard/overview", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert self._EXPECTED_KEYS.issubset(body.keys())
        assert body["total_conversations"] == 0
        assert body["handoff"] == 0
        assert body["handoff_rate"] == 0.0
        assert body["downvote_rate"] == 0.0
        assert body["tool_empty_rate"] == 0.0

    async def test_aggregates_actual_data(self, client, admin_headers, helpers) -> None:
        """写入：3 会话（其中 1 转人工），1 差评，2 工具调用（1 空结果），1 失败回合 → 比率正确。"""
        c1 = await helpers["insert_conversation"](subject_id="U1", mode="ai")
        c2 = await helpers["insert_conversation"](subject_id="U2", mode="human_pending")
        await helpers["insert_conversation"](subject_id="U3", mode="ai")
        # 差评：先建 user→assistant 消息再绑反馈
        await helpers["insert_message"](c1, role="user")
        m_assist = await helpers["insert_message"](c1, role="assistant")
        await helpers["insert_feedback"](c1, m_assist, rating="down")
        # 失败回合：role=user + status=failed
        await helpers["insert_message"](c2, role="user", status="failed")
        # 工具：1 空 / 1 非空
        await helpers["insert_tool_audit"](c1, "query_orders", is_empty=1)
        await helpers["insert_tool_audit"](c1, "query_orders", is_empty=0)

        r = await client.get("/admin/api/v1/dashboard/overview", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total_conversations"] == 3
        assert body["handoff"] == 1
        assert body["handoff_rate"] == pytest.approx(1 / 3)
        assert body["downvote"] == 1
        assert body["downvote_rate"] == 1.0  # 0 up + 1 down → 100%
        assert body["tool_calls"] == 2
        assert body["tool_empty"] == 1
        assert body["tool_empty_rate"] == 0.5
        assert body["failed_turns"] == 1


@pytest.mark.usefixtures("init_self_db")
class TestDashboardOverviewWindow:
    """时间窗 from/to：字典序字符串过滤；窗外数据不应计入。"""

    async def test_window_excludes_outside(self, client, admin_headers, helpers) -> None:
        # 窗外：远古创建一条会话
        await helpers["insert_conversation"](
            subject_id="OLD", created_at="2000-01-01 00:00:00"
        )
        # 窗内：近未来一条
        await helpers["insert_conversation"](
            subject_id="NEW", created_at="2099-01-01 00:00:00"
        )
        r = await client.get(
            "/admin/api/v1/dashboard/overview",
            headers=admin_headers,
            params={"from": "2098-01-01 00:00:00", "to": "2100-01-01 00:00:00"},
        )
        assert r.status_code == 200
        # 窗外的 OLD 不算
        assert r.json()["total_conversations"] == 1

    async def test_window_uses_alias_from_to(self, client, admin_headers) -> None:
        """from/to 是 Query alias（python 关键字 from 不能直接用作参数名）。"""
        r = await client.get(
            "/admin/api/v1/dashboard/overview",
            headers=admin_headers,
            params={"from": "2020-01-01 00:00:00", "to": "2030-01-01 00:00:00"},
        )
        assert r.status_code == 200
