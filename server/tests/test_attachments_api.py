import pytest

from ai_engine.api import attachments as ah

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 8


def test_sniff_accepts_png_jpeg_webp():
    assert ah.sniff_image_mime(PNG) == "image/png"
    assert ah.sniff_image_mime(JPEG) == "image/jpeg"
    assert ah.sniff_image_mime(WEBP) == "image/webp"


def test_sniff_rejects_non_image():
    assert ah.sniff_image_mime(b"%PDF-1.4 not an image") is None


def test_validate_size_over_limit():
    with pytest.raises(ah.AttachmentTooLarge):
        ah.validate_size(b"x" * (5 * 1024 * 1024 + 1))
