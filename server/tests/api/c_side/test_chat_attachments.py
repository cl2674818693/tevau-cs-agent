"""chat 端点的附件参数路径：

- attachment_ids 透传 runtime.run_turn
- _parse_attachment_ids 解析规则：逗号分隔、忽略非数字、按 attachment_max_per_message 截断
- human_takeover 模式下 chat 调 bind_attachments 把图绑到用户消息行
"""

from typing import Any

from httpx import AsyncClient

from ai_engine.persistence import attachments as att_dao
from ai_engine.persistence import conversations as conv_dao

from .conftest import USER_CODE_A, parse_sse


async def _seed_attachment(conv_id: int, uploader: str = USER_CODE_A) -> int:
    """直接在 attachments 表插一行（不走对象存储），模拟"已上传待绑定"。"""
    return await att_dao.create_attachment(
        conv_id, "c", uploader, "k.png", "image/png", 32, "f" * 64
    )


class TestParseAttachmentIds:
    """端点对 attachment_ids 串的解析（_parse_attachment_ids 行为）。"""

    async def test_passes_ids_through_to_run_turn(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        aid1 = await _seed_attachment(conv_id)
        aid2 = await _seed_attachment(conv_id)
        captured: dict[str, Any] = {}

        async def _capture(**kw):
            captured.update(kw)
            yield {"type": "text", "text": "ok"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _capture)

        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "看图",
                "attachment_ids": f"{aid1},{aid2}",
            },
        )
        await parse_sse(r)
        assert captured["attachment_ids"] == [aid1, aid2]

    async def test_ignores_non_numeric_segments(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        aid = await _seed_attachment(conv_id)
        captured: dict[str, Any] = {}

        async def _capture(**kw):
            captured.update(kw)
            yield {"type": "text", "text": "ok"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _capture)
        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "x",
                "attachment_ids": f"abc,{aid},,xyz",
            },
        )
        await parse_sse(r)
        assert captured["attachment_ids"] == [aid]

    async def test_caps_at_max_per_message(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        # 默认 attachment_max_per_message=4：传 5 个 id 只保留前 4
        monkeypatch.setattr(
            "ai_engine.api.chat.settings.attachment_max_per_message", 4
        )
        captured: dict[str, Any] = {}

        async def _capture(**kw):
            captured.update(kw)
            yield {"type": "text", "text": "ok"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _capture)
        await parse_sse(
            await c_client.get(
                "/api/v1/chat",
                params={
                    "conversation_id": conv_id,
                    "message": "x",
                    "attachment_ids": "1,2,3,4,5,6",
                },
            )
        )
        assert captured["attachment_ids"] == [1, 2, 3, 4]

    async def test_no_attachments_means_empty_list(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        captured: dict[str, Any] = {}

        async def _capture(**kw):
            captured.update(kw)
            yield {"type": "text", "text": "ok"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _capture)
        await parse_sse(
            await c_client.get(
                "/api/v1/chat", params={"conversation_id": conv_id, "message": "x"}
            )
        )
        assert captured["attachment_ids"] == []


class TestAttachmentsBindInHumanMode:
    """human_takeover 分支：chat 端点会调 bind_attachments 把附件绑到本条 user 消息。"""

    async def test_attachments_bound_in_human_takeover(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        aid = await _seed_attachment(conv_id)
        await conv_dao.set_mode(conv_id, "human_takeover", assigned_staff_id="S001")
        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "看这个截图",
                "attachment_ids": str(aid),
            },
        )
        await parse_sse(r)
        # bind 后 attachment 应有 message_id（不再 NULL）
        row = await att_dao.get_attachment(aid)
        assert row is not None
        # 反查：取 user 消息 id，应当能从 list_message_attachments 命中
        msgs = await conv_dao.list_messages(conv_id)
        user_msg = next(m for m in msgs if m["role"] == "user")
        bound = await att_dao.list_message_attachments(int(user_msg["id"]))
        assert any(b["id"] == aid for b in bound)

    async def test_other_users_attachment_not_bound(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        """跨 subject 的附件 id 不应被绑（uploader_id 不匹配 → UPDATE 0 行）。"""
        aid_other = await _seed_attachment(conv_id, uploader="U-OTHER")
        await conv_dao.set_mode(conv_id, "human_takeover", assigned_staff_id="S001")
        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "看这个",
                "attachment_ids": str(aid_other),
            },
        )
        await parse_sse(r)
        # 该附件应仍为未绑定（message_id IS NULL → list_for_conversation 不返）
        from ai_engine.persistence.db import fetch_one

        row = await fetch_one(
            "SELECT message_id FROM attachments WHERE id=:aid", {"aid": aid_other}
        )
        assert row is not None
        assert row["message_id"] is None
