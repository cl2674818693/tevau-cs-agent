"""C 端会话生命周期：init + resume + history。

被测端点：
- POST /api/v1/conversations           # 新建/恢复
- GET  /api/v1/conversations/{id}/messages  # 历史回放

覆盖矩阵：
- 未带 token → 游客身份（不返回 401，落回 guest）
- 新建 → 落库 + 默认 mode=ai
- resume 自己的会话 → 同 id 返回 + 携带历史
- resume 别人的会话 → 静默新建（不抛 403）
- resume 已 archived → 同上
- history：归属校验 / role 过滤 / 上限 / 附件挂载
"""

from httpx import AsyncClient

from ai_engine.persistence import attachments as att_dao
from ai_engine.persistence import conversations as conv_dao

from .conftest import auth_headers, TOKEN_B


class TestInitConversation:
    """POST /api/v1/conversations —— 新建 / 恢复。"""

    async def test_creates_new_for_c_user(self, c_client: AsyncClient) -> None:
        r = await c_client.post("/api/v1/conversations", json={})
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["conversation_id"], int)
        assert body["user_type"] == "c"
        assert body["mode"] == "ai"
        assert body["staff_name"] is None
        assert "greeting" in body
        assert body["history_url"].startswith("/api/v1/conversations/")

    async def test_guest_falls_back_when_no_token(self, client: AsyncClient) -> None:
        # 未带 Bearer 时降级为 guest 身份；接口仍 200，user_type='g'
        r = await client.post("/api/v1/conversations", json={})
        assert r.status_code == 200
        assert r.json()["user_type"] == "g"

    async def test_greeting_differs_by_user_type(
        self, c_client: AsyncClient, client: AsyncClient
    ) -> None:
        c_greet = (await c_client.post("/api/v1/conversations", json={})).json()["greeting"]
        g_greet = (await client.post("/api/v1/conversations", json={})).json()["greeting"]
        assert c_greet != g_greet  # C 端 vs 游客文案应不同

    async def test_resume_own_conversation_returns_same_id(
        self, c_client: AsyncClient
    ) -> None:
        first = (await c_client.post("/api/v1/conversations", json={})).json()
        cid = first["conversation_id"]
        again = await c_client.post("/api/v1/conversations", json={"resume": cid})
        assert again.status_code == 200
        assert again.json()["conversation_id"] == cid

    async def test_resume_other_users_conversation_silently_creates_new(
        self, c_client: AsyncClient, other_conv_id: int
    ) -> None:
        # 安全：resume 别人的会话不应命中、也不抛 403；归属校验失败 → 当新建处理
        r = await c_client.post("/api/v1/conversations", json={"resume": other_conv_id})
        assert r.status_code == 200
        new_id = r.json()["conversation_id"]
        assert new_id != other_conv_id

    async def test_resume_archived_conversation_creates_new(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        await conv_dao.archive_conversation(conv_id)
        r = await c_client.post("/api/v1/conversations", json={"resume": conv_id})
        assert r.status_code == 200
        # archived 会话不允许续接，端点会落回新建分支
        assert r.json()["conversation_id"] != conv_id

    async def test_resume_nonexistent_id_creates_new(self, c_client: AsyncClient) -> None:
        r = await c_client.post("/api/v1/conversations", json={"resume": 99_999_999})
        assert r.status_code == 200
        assert r.json()["conversation_id"] != 99_999_999

    async def test_resume_preserves_mode(self, c_client: AsyncClient, conv_id: int) -> None:
        # 切到 human_pending 后 resume 应返回 mode='human_pending'
        await conv_dao.set_mode(conv_id, "human_pending")
        r = await c_client.post("/api/v1/conversations", json={"resume": conv_id})
        assert r.json()["mode"] == "human_pending"

    async def test_limits_payload_exists(self, c_client: AsyncClient) -> None:
        body = (await c_client.post("/api/v1/conversations", json={})).json()
        assert "limits" in body
        assert isinstance(body["limits"], dict)

    async def test_body_optional_keys_accepted(self, c_client: AsyncClient) -> None:
        # body 全空 → 新建；body 缺少 resume 字段也应成功
        r = await c_client.post("/api/v1/conversations", json={"resume": None})
        assert r.status_code == 200


class TestGetHistory:
    """GET /api/v1/conversations/{id}/messages —— 历史回放。"""

    async def test_returns_empty_for_new_conversation(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert r.status_code == 200
        assert r.json()["messages"] == []

    async def test_returns_user_and_assistant_messages(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        # 直接写库，构造一轮已完成对话
        uid = await conv_dao.append_user_turn(conv_id, "我的卡为什么被锁", None)
        await conv_dao.finalize_turn(uid, "done")
        await conv_dao.append_message(
            conv_id, "assistant",
            '[{"type":"text","text":"您的卡被风控规则锁定，请联系人工。"}]',
        )
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        msgs = r.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        # assistant 内部存的是 json blocks，回放时应被还原成纯文本
        assert "锁定" in msgs[1]["content"]

    async def test_skips_processing_user_turn(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        # 半截 user 行（status=processing）应被排除，避免回放问到一半的提问
        await conv_dao.append_user_turn(conv_id, "incomplete", None)
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert r.json()["messages"] == []

    async def test_skips_failed_user_turn(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        uid = await conv_dao.append_user_turn(conv_id, "boom", None)
        await conv_dao.finalize_turn(uid, "failed", "INTERNAL_ERROR")
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert r.json()["messages"] == []

    async def test_skips_ai_draft_and_system_roles(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        # ai_draft / system 不属于 _USER_FACING_ROLES，应被滤掉
        await conv_dao.save_ai_draft(conv_id, "草稿内容")
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert r.json()["messages"] == []

    async def test_returns_human_agent_messages(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        await conv_dao.append_human_message(conv_id, "S001", "您好，我是客服小明")
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        msgs = r.json()["messages"]
        assert msgs[-1]["role"] == "human_agent"
        assert "客服小明" in msgs[-1]["content"]

    async def test_attachments_inlined(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        # 用户消息 + 一张图（uploader 必须等于 subject_id 才能被 bind 命中）
        uid = await conv_dao.append_user_turn(conv_id, "看这张图", None)
        await conv_dao.finalize_turn(uid, "done")
        from .conftest import USER_CODE_A
        aid = await att_dao.create_attachment(
            conv_id, "c", USER_CODE_A, "k.png", "image/png", 100, "x" * 64
        )
        bound = await att_dao.bind_attachments(uid, conv_id, USER_CODE_A, [aid])
        assert bound and bound[0]["id"] == aid
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        msgs = r.json()["messages"]
        assert msgs[0]["attachments"] == [{"id": aid, "mime": "image/png"}]

    async def test_skips_empty_message_no_attachment(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        # 纯空消息 + 无附件 → 跳过
        await conv_dao.append_message(conv_id, "assistant", "[]")
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert r.json()["messages"] == []

    async def test_forbids_other_users_history(
        self, c_client: AsyncClient, other_conv_id: int
    ) -> None:
        r = await c_client.get(f"/api/v1/conversations/{other_conv_id}/messages")
        assert r.status_code == 403

    async def test_guest_cannot_access_c_users_history(
        self, client: AsyncClient, conv_id: int
    ) -> None:
        # 不带 token → 游客身份；游客访问 C 用户的会话应 403（user_type 不匹配）
        r = await client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert r.status_code == 403

    async def test_wrong_token_cannot_access(
        self, client: AsyncClient, conv_id: int
    ) -> None:
        r = await client.get(
            f"/api/v1/conversations/{conv_id}/messages", headers=auth_headers(TOKEN_B)
        )
        assert r.status_code == 403

    async def test_nonexistent_conversation_returns_403(
        self, c_client: AsyncClient
    ) -> None:
        # 端点把不存在的会话也归为"non-owned" → 403（防探测；同 chat 行为一致）
        r = await c_client.get("/api/v1/conversations/99999999/messages")
        assert r.status_code == 403

    async def test_history_capped_at_max(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        # 写 220 条 user 行（已完成）；接口最多返回最近 200 条
        for i in range(220):
            uid = await conv_dao.append_user_turn(conv_id, f"msg-{i}", None)
            await conv_dao.finalize_turn(uid, "done")
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        msgs = r.json()["messages"]
        assert len(msgs) == 200
        # 最近的一定在最后；最早的 20 条应被截掉
        assert msgs[-1]["content"] == "msg-219"
        assert msgs[0]["content"] == "msg-20"
