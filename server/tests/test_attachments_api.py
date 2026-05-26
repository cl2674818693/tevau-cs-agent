import pytest
from httpx import ASGITransport, AsyncClient

from ai_engine.api import attachments as ah
from ai_engine.storage import object_store as om

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 8

BU = "BU00243780"  # seeded B 端身份（见 tests/fixtures/seed.sql）


class _FakeStore:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    async def put(self, key, data, content_type):
        self.data[key] = data

    async def get(self, key):
        return self.data[key]

    async def presigned_get(self, key, ttl_seconds):
        return f"https://signed.example/{key}"


async def _client():
    from ai_engine import main as main_mod

    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://test")


async def _new_conv(client) -> int:
    r = await client.post("/api/v1/conversations", json={}, headers={"X-BU-ID": BU})
    return r.json()["conversation_id"]


def test_sniff_accepts_png_jpeg_webp():
    assert ah.sniff_image_mime(PNG) == "image/png"
    assert ah.sniff_image_mime(JPEG) == "image/jpeg"
    assert ah.sniff_image_mime(WEBP) == "image/webp"


def test_sniff_rejects_non_image():
    assert ah.sniff_image_mime(b"%PDF-1.4 not an image") is None


def test_validate_size_over_limit():
    with pytest.raises(ah.AttachmentTooLarge):
        ah.validate_size(b"x" * (5 * 1024 * 1024 + 1))


async def test_user_upload_and_view(seeded_db):
    om.set_object_store(_FakeStore())
    async with await _client() as client:
        conv_id = await _new_conv(client)
        files = {"file": ("s.png", PNG, "image/png")}
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/attachments", files=files, headers={"X-BU-ID": BU}
        )
        assert r.status_code == 200
        aid = r.json()["attachment_id"]

        r2 = await client.get(
            f"/api/v1/conversations/{conv_id}/attachments/{aid}",
            headers={"X-BU-ID": BU},
            follow_redirects=False,
        )
        assert r2.status_code in (302, 307)
        assert "signed.example" in r2.headers["location"]


async def test_user_upload_rejects_non_image(seeded_db):
    om.set_object_store(_FakeStore())
    async with await _client() as client:
        conv_id = await _new_conv(client)
        files = {"file": ("x.pdf", b"%PDF-1.4 not an image at all", "application/pdf")}
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/attachments", files=files, headers={"X-BU-ID": BU}
        )
        assert r.status_code == 415
