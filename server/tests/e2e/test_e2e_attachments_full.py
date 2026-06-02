"""E2E 剧本 #12：图片附件全链路 上传 → 发消息带图 → 座席端可见 → 重新拉字节。

剧本梗概：
    1. 用 in-memory FakeObjectStore 替换真实 S3/MinIO。
    2. 用户 POST /api/v1/conversations/{id}/attachments 上传 PNG → 返回 attachment_id。
    3. 用户 GET /api/v1/chat?attachment_ids=... → 触发 attachment 与消息绑定。
       这里 stub run_turn 模拟 LLM 收到附件参数。
    4. 用户 GET /api/v1/conversations/{id}/messages → history 包含该消息的 attachments 列表。
    5. 用户 GET /api/v1/conversations/{id}/attachments/{aid} → 回 PNG 字节。
    6. 转人工后，座席 GET /staff/api/v1/conversations/{id}/attachments/{aid} → 同样能看图。

异常分支：
    - 上传超大字节 → 413。
    - 上传非图片字节 → 415。
    - 越权调他人会话的 attachment → 404 / 403。
    - 跨会话的 attachment_id 在 chat 端点 bind 时被静默丢弃（uploader_id/conv_id 不匹配）。
"""


import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_engine.main import app

from .conftest import TOKEN_B, c_headers, stub_run_turn

# ── Fake object store（替换 _store 全局）─────────────────────────────────


class _FakeObjectStore:
    """内存版对象存储：put 写 dict，get 直接拿回 bytes。"""

    def __init__(self) -> None:
        self.bucket: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.bucket[key] = data

    async def get(self, key: str) -> bytes:
        return self.bucket[key]

    async def presigned_get(self, key: str, ttl_seconds: int) -> str:
        return f"http://fake/{key}?ttl={ttl_seconds}"


# 1x1 PNG (RFC 2083 minimal)
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
    b"\xc0\xc0\xc0\x00\x00\x00\x03\x00\x01\xa6\xc6\xd9\x91\x00\x00\x00\x00"
    b"IEND\xaeB`\x82"
)


@pytest.fixture
def fake_store(monkeypatch):
    """注入内存对象存储，避免连真实 MinIO/S3。"""
    from ai_engine.storage import object_store as os_mod

    store = _FakeObjectStore()
    monkeypatch.setattr(os_mod, "_store", store)
    yield store
    monkeypatch.setattr(os_mod, "_store", None)


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    return int(r.json()["conversation_id"])


class TestAttachmentsHappyPath:
    async def test_upload_and_view_as_user(
        self, c_client: AsyncClient, conv_id: int, fake_store
    ) -> None:
        # 1. 上传
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments",
            files={"file": ("a.png", _PNG_BYTES, "image/png")},
        )
        assert r.status_code == 200
        aid = int(r.json()["attachment_id"])
        assert aid > 0
        assert fake_store.bucket, "对象存储应被写入"

        # 2. 用户取字节
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/attachments/{aid}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.content == _PNG_BYTES

    async def test_send_message_with_attachment_binds_and_appears_in_history(
        self, c_client: AsyncClient, conv_id: int, fake_store, monkeypatch
    ) -> None:
        stub_run_turn(monkeypatch, [{"type": "text", "text": "收到您的图片了"}])
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments",
            files={"file": ("a.png", _PNG_BYTES, "image/png")},
        )
        aid = int(r.json()["attachment_id"])

        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "看看这张图",
                "attachment_ids": str(aid),
            },
        )
        assert r.status_code == 200

        # history 包含该消息 + attachments
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert r.status_code == 200
        msgs = r.json()["messages"]
        user_msgs = [m for m in msgs if m["role"] == "user"]
        assert user_msgs
        first_user = user_msgs[0]
        assert any(a["id"] == aid for a in first_user["attachments"])

    async def test_staff_can_view_attachment_after_takeover(
        self,
        c_client: AsyncClient,
        conv_id: int,
        fake_store,
        seeded_agent,
        make_staff_client,
    ) -> None:
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments",
            files={"file": ("a.png", _PNG_BYTES, "image/png")},
        )
        aid = int(r.json()["attachment_id"])

        # 转人工 + 接管（这两步 attachment 仍归属用户，staff_view_attachment 端点本身不要求接管）
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "?"}
        )
        sc = make_staff_client(seeded_agent, "agent")
        await sc.post(f"/staff/api/v1/conversations/{conv_id}/take")

        r = await sc.get(f"/staff/api/v1/conversations/{conv_id}/attachments/{aid}")
        assert r.status_code == 200
        assert r.content == _PNG_BYTES


class TestAttachmentsErrorPaths:
    async def test_too_large_returns_413(
        self, c_client: AsyncClient, conv_id: int, fake_store, monkeypatch
    ) -> None:
        from ai_engine.config import settings

        monkeypatch.setattr(settings, "attachment_max_bytes", 16, raising=False)
        # 上面 _PNG_BYTES 远超 16 bytes
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments",
            files={"file": ("big.png", _PNG_BYTES, "image/png")},
        )
        assert r.status_code == 413

    async def test_non_image_returns_415(
        self, c_client: AsyncClient, conv_id: int, fake_store
    ) -> None:
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments",
            files={"file": ("hack.txt", b"plain text not an image", "text/plain")},
        )
        assert r.status_code == 415

    async def test_other_user_cannot_view_attachment(
        self, c_client: AsyncClient, conv_id: int, fake_store
    ) -> None:
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments",
            files={"file": ("a.png", _PNG_BYTES, "image/png")},
        )
        aid = int(r.json()["attachment_id"])

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=c_headers(TOKEN_B)
        ) as cb:
            r = await cb.get(f"/api/v1/conversations/{conv_id}/attachments/{aid}")
            # _authorize_conversation 先校验会话归属 → 403
            assert r.status_code == 403

    async def test_attachment_id_from_other_conv_is_silently_skipped_on_bind(
        self,
        c_client: AsyncClient,
        conv_id: int,
        fake_store,
        monkeypatch,
    ) -> None:
        """跨会话/跨身份的 attachment_id 在 bind 时不通过 WHERE 条件 → 静默丢弃，
        history 不包含、对话流不报错。"""
        stub_run_turn(monkeypatch, [{"type": "text", "text": "ok"}])

        # B 的会话 + 上传
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=c_headers(TOKEN_B)
        ) as cb:
            rb = await cb.post("/api/v1/conversations", json={})
            cid_b = int(rb.json()["conversation_id"])
            rb = await cb.post(
                f"/api/v1/conversations/{cid_b}/attachments",
                files={"file": ("a.png", _PNG_BYTES, "image/png")},
            )
            aid_b = int(rb.json()["attachment_id"])

        # A 在自己 conv 发消息引用 B 的 attachment_id：不报错但 bind 不上
        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "?",
                "attachment_ids": str(aid_b),
            },
        )
        assert r.status_code == 200

        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        msgs = r.json()["messages"]
        # 没有任何附件出现在 A 的 history
        for m in msgs:
            assert m["attachments"] == []

    async def test_attachment_max_per_message_truncates(
        self, c_client: AsyncClient, conv_id: int, fake_store, monkeypatch
    ) -> None:
        """attachment_ids 超过 max_per_message → 按上限截断（剩余被丢弃）。"""
        from ai_engine.config import settings

        monkeypatch.setattr(settings, "attachment_max_per_message", 2, raising=False)
        stub_run_turn(monkeypatch, [{"type": "text", "text": "ok"}])

        # 上传 3 张
        ids: list[int] = []
        for _ in range(3):
            r = await c_client.post(
                f"/api/v1/conversations/{conv_id}/attachments",
                files={"file": ("a.png", _PNG_BYTES, "image/png")},
            )
            ids.append(int(r.json()["attachment_id"]))

        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "三张",
                "attachment_ids": ",".join(map(str, ids)),
            },
        )
        assert r.status_code == 200

        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        user = next(m for m in r.json()["messages"] if m["role"] == "user")
        # 前两张绑定成功；第三张被截断
        assert len(user["attachments"]) == 2
        bound_ids = {a["id"] for a in user["attachments"]}
        assert bound_ids == set(ids[:2])
