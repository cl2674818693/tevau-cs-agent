"""API: 座席端附件（attachments.py 中 staff 前缀的端点）。

被测端点：
- POST /staff/api/v1/conversations/{id}/attachments        座席上传
- GET  /staff/api/v1/conversations/{id}/attachments/{aid}  座席查看

C 端附件端点（/api/v1/...）在 c_side 测试覆盖，本组只测座席侧（require_staff）。

策略：用 set_object_store 注入内存假 store，避免依赖真实 S3/MinIO。

异常矩阵：
- 未登录 → 401
- 上传不是 PNG/JPEG/GIF/WebP → 415
- 超过 5MB → 413
- 上传给非自己的会话 → 403
- 取附件 aid 不存在 → 404
- 取附件 aid 不属于该会话 → 404
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.attachments import router as attachments_router
from ai_engine.config import settings
from ai_engine.storage.object_store import set_object_store

from .conftest import insert_conversation


# ── 假对象存储（内存 dict） ──────────────────────────────────────────────────
class _FakeStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self._data[key] = (data, content_type)

    async def get(self, key: str) -> bytes:
        return self._data[key][0]

    async def presigned_get(self, key: str, ttl_seconds: int) -> str:
        return f"https://fake/{key}"


@pytest.fixture(autouse=True)
def _patch_store():
    fake = _FakeStore()
    set_object_store(fake)
    yield fake
    set_object_store(None)  # type: ignore[arg-type]  # reset 让真实 S3 客户端下次重建


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(attachments_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── 各类图片 magic bytes ────────────────────────────────────────────────────
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 100
GIF_BYTES = b"GIF89a" + b"\x00" * 100
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
TXT_BYTES = b"this is a text file, not an image\n" * 10


class TestStaffUploadAuth:
    async def test_unauthenticated_401(self, init_self_db, client) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("a.png", PNG_BYTES, "image/png")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments", files=files
        )
        assert resp.status_code == 401


class TestStaffUploadHappyPath:
    async def test_upload_png(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("a.png", PNG_BYTES, "image/png")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent_headers,
        )
        assert resp.status_code == 200
        assert "attachment_id" in resp.json()

    async def test_upload_jpeg(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("a.jpg", JPEG_BYTES, "image/jpeg")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent_headers,
        )
        assert resp.status_code == 200

    async def test_upload_gif(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("a.gif", GIF_BYTES, "image/gif")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent_headers,
        )
        assert resp.status_code == 200

    async def test_upload_webp(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("a.webp", WEBP_BYTES, "image/webp")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent_headers,
        )
        assert resp.status_code == 200


class TestStaffUploadValidation:
    async def test_upload_non_image_415(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("x.txt", TXT_BYTES, "text/plain")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent_headers,
        )
        assert resp.status_code == 415
        assert "unsupported" in resp.json()["detail"]

    async def test_upload_too_large_413(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        # max 默认 5MB；构造 5MB+1
        big = PNG_BYTES + b"\x00" * (settings.attachment_max_bytes + 1)
        files = {"file": ("big.png", big, "image/png")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent_headers,
        )
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"]

    async def test_upload_fake_content_type_validated_by_magic(
        self, init_self_db, client, agent_headers
    ) -> None:
        """前端 Content-Type 撒谎说 image/png 但实际 bytes 是 txt → magic 嗅探拒绝 415。"""
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("fake.png", TXT_BYTES, "image/png")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent_headers,
        )
        assert resp.status_code == 415


class TestStaffUploadConversationOwnership:
    async def test_upload_not_my_conversation_403(
        self, init_self_db, client, agent2_headers
    ) -> None:
        """会话指派给 agent-1，agent-2 想上传 → 403。"""
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("a.png", PNG_BYTES, "image/png")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent2_headers,
        )
        assert resp.status_code == 403

    async def test_upload_when_mode_not_takeover_403(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(mode="ai")
        files = {"file": ("a.png", PNG_BYTES, "image/png")}
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent_headers,
        )
        assert resp.status_code == 403


class TestStaffViewAttachment:
    async def test_view_happy(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("a.png", PNG_BYTES, "image/png")}
        up = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files=files, headers=agent_headers,
        )
        aid = up.json()["attachment_id"]
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/attachments/{aid}",
            headers=agent_headers,
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == PNG_BYTES

    async def test_view_unknown_aid_404(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/attachments/9999",
            headers=agent_headers,
        )
        assert resp.status_code == 404

    async def test_view_aid_from_other_conversation_404(
        self, init_self_db, client, agent_headers
    ) -> None:
        """aid 属于 conv_a，请求 conv_b/attachments/aid → 404（防 IDOR）。"""
        cid_a = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        cid_b = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        files = {"file": ("a.png", PNG_BYTES, "image/png")}
        up = await client.post(
            f"/staff/api/v1/conversations/{cid_a}/attachments",
            files=files, headers=agent_headers,
        )
        aid = up.json()["attachment_id"]
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid_b}/attachments/{aid}",
            headers=agent_headers,
        )
        assert resp.status_code == 404

    async def test_view_unauthenticated_401(self, init_self_db, client) -> None:
        cid = await insert_conversation()
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/attachments/1"
        )
        assert resp.status_code == 401
