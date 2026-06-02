"""C 端附件 API：上传 + 查看（同源代理图片字节）。

被测：
- POST /api/v1/conversations/{cid}/attachments
- GET  /api/v1/conversations/{cid}/attachments/{aid}

对象存储用 fake store（不连 MinIO/S3）；上传只验 magic byte + 大小。
"""

from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from ai_engine.persistence import attachments as att_dao
from ai_engine.storage import object_store as _os

from .conftest import TOKEN_B, auth_headers


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # 最小合法 PNG magic
JPEG_HEADER = b"\xff\xd8\xff" + b"\x00" * 16
GIF_HEADER = b"GIF89a" + b"\x00" * 16
WEBP_HEADER = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 16


class FakeStore:
    """内存对象存储替身：put 记录字节，get 按 key 取回。"""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def presigned_get(self, key: str, ttl_seconds: int) -> str:
        return f"http://fake/{key}"


@pytest.fixture
def fake_store(monkeypatch) -> FakeStore:
    store = FakeStore()
    _os.set_object_store(store)
    yield store
    # 清掉单例 → 下一个用例自己装新的
    _os.set_object_store(None)  # type: ignore[arg-type]


class TestUploadAttachment:
    async def test_uploads_png(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        files = {"file": ("a.png", PNG_HEADER, "image/png")}
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments", files=files
        )
        assert r.status_code == 200
        aid = r.json()["attachment_id"]
        # DAO 应能取出（mime=image/png）
        row = await att_dao.get_attachment(aid)
        assert row and row["mime"] == "image/png"
        # 字节落到 fake store
        assert any(v == PNG_HEADER for v in fake_store.objects.values())

    async def test_uploads_jpeg(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        files = {"file": ("a.jpg", JPEG_HEADER, "image/jpeg")}
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments", files=files
        )
        assert r.status_code == 200

    async def test_uploads_gif(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        files = {"file": ("a.gif", GIF_HEADER, "image/gif")}
        assert (
            await c_client.post(
                f"/api/v1/conversations/{conv_id}/attachments", files=files
            )
        ).status_code == 200

    async def test_uploads_webp(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        files = {"file": ("a.webp", WEBP_HEADER, "image/webp")}
        assert (
            await c_client.post(
                f"/api/v1/conversations/{conv_id}/attachments", files=files
            )
        ).status_code == 200

    async def test_rejects_oversize_image(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore, monkeypatch
    ) -> None:
        # 把单图上限调到 100 字节
        monkeypatch.setattr(
            "ai_engine.api.attachments.settings.attachment_max_bytes", 100
        )
        big = PNG_HEADER + b"\x00" * 200
        files = {"file": ("big.png", big, "image/png")}
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments", files=files
        )
        assert r.status_code == 413

    async def test_rejects_unknown_mime(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        # magic byte 不是已知图片 → 415
        files = {"file": ("a.bin", b"NOT-AN-IMAGE", "application/octet-stream")}
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments", files=files
        )
        assert r.status_code == 415

    async def test_rejects_misleading_content_type(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        """客户端声称是 image/png 但 bytes 不是 PNG → 同样 415（只信 magic byte）。"""
        files = {"file": ("fake.png", b"<html>evil</html>", "image/png")}
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments", files=files
        )
        assert r.status_code == 415

    async def test_unauth_returns_403(
        self, client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        files = {"file": ("a.png", PNG_HEADER, "image/png")}
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/attachments", files=files
        )
        # 不带 token → guest → 归属校验失败 → 403
        assert r.status_code == 403

    async def test_other_user_cannot_upload_to_my_conv(
        self, client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        files = {"file": ("a.png", PNG_HEADER, "image/png")}
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/attachments",
            files=files,
            headers=auth_headers(TOKEN_B),
        )
        assert r.status_code == 403

    async def test_missing_file_returns_422(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        r = await c_client.post(f"/api/v1/conversations/{conv_id}/attachments")
        assert r.status_code == 422


class TestViewAttachment:
    @pytest_asyncio.fixture
    async def uploaded_id(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> int:
        files = {"file": ("a.png", PNG_HEADER, "image/png")}
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/attachments", files=files
        )
        return int(r.json()["attachment_id"])

    async def test_returns_bytes_with_correct_mime(
        self,
        c_client: AsyncClient,
        conv_id: int,
        uploaded_id: int,
        fake_store: FakeStore,
    ) -> None:
        r = await c_client.get(
            f"/api/v1/conversations/{conv_id}/attachments/{uploaded_id}"
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.content == PNG_HEADER

    async def test_other_user_forbidden(
        self,
        client: AsyncClient,
        conv_id: int,
        uploaded_id: int,
        fake_store: FakeStore,
    ) -> None:
        r = await client.get(
            f"/api/v1/conversations/{conv_id}/attachments/{uploaded_id}",
            headers=auth_headers(TOKEN_B),
        )
        assert r.status_code == 403

    async def test_no_auth_forbidden(
        self,
        client: AsyncClient,
        conv_id: int,
        uploaded_id: int,
        fake_store: FakeStore,
    ) -> None:
        r = await client.get(
            f"/api/v1/conversations/{conv_id}/attachments/{uploaded_id}"
        )
        assert r.status_code == 403

    async def test_nonexistent_returns_404(
        self, c_client: AsyncClient, conv_id: int, fake_store: FakeStore
    ) -> None:
        r = await c_client.get(
            f"/api/v1/conversations/{conv_id}/attachments/99999999"
        )
        assert r.status_code == 404

    async def test_attachment_belongs_to_other_conv_returns_404(
        self,
        c_client: AsyncClient,
        conv_id: int,
        uploaded_id: int,
        fake_store: FakeStore,
    ) -> None:
        """attachment 存在但 conversation_id 不匹配（伪造 URL）→ 404。"""
        # 用同 user 起第二条会话
        r0 = await c_client.post("/api/v1/conversations", json={})
        other_cid = r0.json()["conversation_id"]
        r = await c_client.get(
            f"/api/v1/conversations/{other_cid}/attachments/{uploaded_id}"
        )
        assert r.status_code == 404
