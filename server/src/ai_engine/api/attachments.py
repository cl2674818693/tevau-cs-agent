import hashlib
import uuid

from fastapi import APIRouter

from ai_engine.config import settings

router = APIRouter()

# magic-byte 嗅探：只认这几种图，不信客户端 Content-Type
_MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]


class AttachmentTooLarge(Exception):
    pass


class AttachmentBadType(Exception):
    pass


def sniff_image_mime(data: bytes) -> str | None:
    for sig, mime in _MAGIC:
        if data.startswith(sig):
            return mime
    # webp: RIFF....WEBP
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_size(data: bytes) -> None:
    if len(data) > settings.attachment_max_bytes:
        raise AttachmentTooLarge


_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}


def make_object_key(conv_id: int, mime: str) -> str:
    return f"uploads/{conv_id}/{uuid.uuid4().hex}.{_EXT[mime]}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
