"""业务洞察 /staff/api/v1/insights/*。

被测：insights.gaps / tools / gap_convs（require_staff，任何已签名 staff 都能看）。
覆盖：鉴权（任意 staff 通过；无 token 401）；空数据 0/[]；写入后聚合计数正确；
     time window 过滤；tool_health 的 empty_rate；gap-conversations 各 kind 白名单 + 非法 kind 400；
     limit 边界 422；按 created_at 字典序窗口。
"""

import pytest


@pytest.mark.usefixtures("init_self_db")
class TestInsightsAuth:
    """require_staff：任何已验签 staff 即可访问（不区分角色）。"""

    @pytest.mark.parametrize(
        "path",
        [
            "/staff/api/v1/insights/knowledge-gaps",
            "/staff/api/v1/insights/tool-health",
            "/staff/api/v1/insights/gap-conversations?kind=out_of_scope",
        ],
    )
    async def test_no_token_returns_401(self, client, path: str) -> None:
        r = await client.get(path)
        assert r.status_code == 401

    @pytest.mark.parametrize(
        "role", ["agent", "senior", "engineer", "supervisor", "manager", "admin"]
    )
    async def test_any_staff_can_access(
        self, client, auth_headers, role: str
    ) -> None:
        r = await client.get(
            "/staff/api/v1/insights/knowledge-gaps", headers=auth_headers(role),
        )
        assert r.status_code == 200

    async def test_invalid_token_returns_401(self, client) -> None:
        r = await client.get(
            "/staff/api/v1/insights/knowledge-gaps",
            headers={"Authorization": "Bearer not.a.real.jwt"},
        )
        assert r.status_code == 401


@pytest.mark.usefixtures("init_self_db")
class TestKnowledgeGaps:
    async def test_empty_returns_all_zero(self, client, admin_headers) -> None:
        r = await client.get(
            "/staff/api/v1/insights/knowledge-gaps", headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["out_of_scope"] == 0
        assert body["failed_turns"] == 0
        assert body["thumbs_down"] == 0
        assert body["human_handoff"] == 0
        # 时间窗 echo 出来
        assert body["from"] is None
        assert body["to"] is None

    async def test_counts_each_signal(
        self, client, admin_headers, helpers
    ) -> None:
        # out_of_scope：user 消息且 topic_verdict='no'
        c1 = await helpers["insert_conversation"](subject_id="U1")
        await helpers["insert_message"](c1, role="user", topic_verdict="no")
        await helpers["insert_message"](c1, role="user", topic_verdict="no")
        # failed_turns：user 消息且 status='failed'
        await helpers["insert_message"](c1, role="user", status="failed")
        # thumbs_down：message_feedback rating='down'
        m_assist = await helpers["insert_message"](c1, role="assistant")
        await helpers["insert_feedback"](c1, m_assist, rating="down")
        await helpers["insert_feedback"](c1, m_assist, rating="up")  # up 不计
        # human_handoff：conversations mode IN human_pending / human_takeover
        await helpers["insert_conversation"](subject_id="U2", mode="human_pending")
        await helpers["insert_conversation"](subject_id="U3", mode="human_takeover")
        await helpers["insert_conversation"](subject_id="U4", mode="ai")  # 不算

        r = await client.get(
            "/staff/api/v1/insights/knowledge-gaps", headers=admin_headers,
        )
        body = r.json()
        assert body["out_of_scope"] == 2
        assert body["failed_turns"] == 1
        assert body["thumbs_down"] == 1
        assert body["human_handoff"] == 2

    async def test_time_window_filters(
        self, client, admin_headers, helpers
    ) -> None:
        c = await helpers["insert_conversation"](subject_id="U1")
        await helpers["insert_message"](
            c, role="user", topic_verdict="no",
            created_at="2000-01-01 00:00:00",
        )
        await helpers["insert_message"](
            c, role="user", topic_verdict="no",
            created_at="2099-01-01 00:00:00",
        )
        r = await client.get(
            "/staff/api/v1/insights/knowledge-gaps",
            headers=admin_headers,
            params={"from": "2098-01-01 00:00:00", "to": "2100-01-01 00:00:00"},
        )
        body = r.json()
        assert body["out_of_scope"] == 1
        assert body["from"] == "2098-01-01 00:00:00"
        assert body["to"] == "2100-01-01 00:00:00"


@pytest.mark.usefixtures("init_self_db")
class TestToolHealth:
    async def test_empty_returns_empty_list(self, client, admin_headers) -> None:
        r = await client.get(
            "/staff/api/v1/insights/tool-health", headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["tools"] == []

    async def test_aggregates_per_tool(
        self, client, admin_headers, helpers
    ) -> None:
        cid = await helpers["insert_conversation"]()
        # query_orders: 3 调用 / 1 空 / 0 拒
        await helpers["insert_tool_audit"](cid, "query_orders", is_empty=0)
        await helpers["insert_tool_audit"](cid, "query_orders", is_empty=1)
        await helpers["insert_tool_audit"](cid, "query_orders", is_empty=0)
        # query_kyc: 2 调用 / 0 空 / 1 拒
        await helpers["insert_tool_audit"](cid, "query_kyc", is_empty=0, rejected=1)
        await helpers["insert_tool_audit"](cid, "query_kyc", is_empty=0)

        r = await client.get(
            "/staff/api/v1/insights/tool-health", headers=admin_headers,
        )
        tools = {t["tool_name"]: t for t in r.json()["tools"]}
        assert tools["query_orders"]["calls"] == 3
        assert tools["query_orders"]["empty"] == 1
        assert tools["query_orders"]["rejected"] == 0
        assert tools["query_orders"]["empty_rate"] == pytest.approx(1 / 3)
        assert tools["query_kyc"]["calls"] == 2
        assert tools["query_kyc"]["rejected"] == 1

    async def test_is_empty_null_counted_as_non_empty(
        self, client, admin_headers, helpers
    ) -> None:
        """历史行 is_empty=NULL 不应被算作 empty（SQL 用 CASE WHEN is_empty=1 THEN 1 ELSE 0）。"""
        cid = await helpers["insert_conversation"]()
        await helpers["insert_tool_audit"](cid, "t_null", is_empty=None)
        r = await client.get(
            "/staff/api/v1/insights/tool-health", headers=admin_headers,
        )
        t = next(t for t in r.json()["tools"] if t["tool_name"] == "t_null")
        assert t["calls"] == 1
        assert t["empty"] == 0
        assert t["empty_rate"] == 0.0


@pytest.mark.usefixtures("init_self_db")
class TestGapConversations:
    async def test_missing_kind_returns_422(self, client, admin_headers) -> None:
        r = await client.get(
            "/staff/api/v1/insights/gap-conversations", headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_invalid_kind_returns_400(self, client, admin_headers) -> None:
        """kind 不在白名单 → DAO ValueError → 400（不拼进 SQL）。"""
        r = await client.get(
            "/staff/api/v1/insights/gap-conversations",
            params={"kind": "robots; DROP TABLE"},
            headers=admin_headers,
        )
        assert r.status_code == 400

    @pytest.mark.parametrize(
        "kind", ["out_of_scope", "failed", "thumbs_down", "human_handoff"]
    )
    async def test_valid_kinds_return_200(
        self, client, admin_headers, kind: str
    ) -> None:
        r = await client.get(
            "/staff/api/v1/insights/gap-conversations",
            params={"kind": kind},
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == kind
        assert body["conversations"] == []  # 空 DB → 空列表

    async def test_out_of_scope_lists_conversations(
        self, client, admin_headers, helpers
    ) -> None:
        c1 = await helpers["insert_conversation"](subject_id="U1")
        c2 = await helpers["insert_conversation"](subject_id="U2")
        await helpers["insert_message"](c1, role="user", topic_verdict="no")
        await helpers["insert_message"](c2, role="user", topic_verdict="no")
        await helpers["insert_message"](c2, role="user", topic_verdict="no")
        r = await client.get(
            "/staff/api/v1/insights/gap-conversations",
            params={"kind": "out_of_scope"},
            headers=admin_headers,
        )
        rows = r.json()["conversations"]
        assert {row["conversation_id"] for row in rows} == {c1, c2}
        # 每行带 last_at
        assert all("last_at" in row for row in rows)

    async def test_human_handoff_uses_conversation_table(
        self, client, admin_headers, helpers
    ) -> None:
        c = await helpers["insert_conversation"](
            subject_id="HOI", mode="human_pending",
        )
        await helpers["insert_conversation"](subject_id="AI", mode="ai")
        r = await client.get(
            "/staff/api/v1/insights/gap-conversations",
            params={"kind": "human_handoff"},
            headers=admin_headers,
        )
        rows = r.json()["conversations"]
        assert [row["conversation_id"] for row in rows] == [c]

    @pytest.mark.parametrize("limit", [0, -1, 201])
    async def test_limit_out_of_range_422(
        self, client, admin_headers, limit: int
    ) -> None:
        r = await client.get(
            "/staff/api/v1/insights/gap-conversations",
            params={"kind": "out_of_scope", "limit": limit},
            headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_limit_caps_result(self, client, admin_headers, helpers) -> None:
        for i in range(5):
            c = await helpers["insert_conversation"](subject_id=f"U{i}")
            await helpers["insert_message"](c, role="user", topic_verdict="no")
        r = await client.get(
            "/staff/api/v1/insights/gap-conversations",
            params={"kind": "out_of_scope", "limit": 2},
            headers=admin_headers,
        )
        assert len(r.json()["conversations"]) == 2
