import hashlib
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from ai_engine.auth.staff_session import require_staff
from ai_engine.config import settings
from ai_engine.persistence import attachments as att_dao
from ai_engine.persistence import conversations as conv_dao
from ai_engine.storage.object_store import get_object_store

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


async def _store_upload(
    conv_id: int, uploader_type: str, uploader_id: str, file: UploadFile
) -> int:
    """读取上传文件→校验大小/类型→落对象存储→建 attachment 行(message_id NULL)。"""
    data = await file.read()
    validate_size(data)  # 抛 AttachmentTooLarge
    mime = sniff_image_mime(data)
    if mime is None:
        raise AttachmentBadType
    key = make_object_key(conv_id, mime)
    await get_object_store().put(key, data, mime)
    return await att_dao.create_attachment(
        conv_id, uploader_type, uploader_id, key, mime, len(data), sha256_hex(data)
    )


@router.post("/api/v1/conversations/{conv_id}/attachments")
async def upload_attachment(
    conv_id: int, request: Request, file: UploadFile = File(...)
) -> dict[str, int]:
    # 延迟 import 规避循环依赖（chat.py 顶部已 import 本模块的兄弟模块链路）
    from ai_engine.api.chat import _authorize_conversation

    user_type, subject_id = await _authorize_conversation(request, conv_id)
    try:
        aid = await _store_upload(conv_id, user_type, subject_id, file)
    except AttachmentTooLarge:
        raise HTTPException(413, "image too large") from None
    except AttachmentBadType:
        raise HTTPException(415, "unsupported image type") from None
    return {"attachment_id": aid}


@router.get("/api/v1/conversations/{conv_id}/attachments/{aid}")
async def view_attachment(conv_id: int, aid: int, request: Request) -> RedirectResponse:
    from ai_engine.api.chat import _authorize_conversation

    await _authorize_conversation(request, conv_id)
    row = await att_dao.get_attachment(aid)
    if not row or row["conversation_id"] != conv_id:
        raise HTTPException(404, "not found")
    url = await get_object_store().presigned_get(
        row["object_key"], settings.attachment_url_ttl_seconds
    )
    return RedirectResponse(url)


async def _assert_staff_conv(conv_id: int, staff_sub: str) -> None:
    mode, sid = await conv_dao.get_mode(conv_id)
    if mode != "human_takeover" or sid != staff_sub:
        raise HTTPException(403, "not your conversation")


@router.post("/staff/api/v1/conversations/{conv_id}/attachments")
async def staff_upload_attachment(
    conv_id: int, file: UploadFile = File(...), staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, int]:
    await _assert_staff_conv(conv_id, staff["sub"])
    try:
        aid = await _store_upload(conv_id, "staff", staff["sub"], file)
    except AttachmentTooLarge:
        raise HTTPException(413, "image too large") from None
    except AttachmentBadType:
        raise HTTPException(415, "unsupported image type") from None
    return {"attachment_id": aid}


@router.get("/staff/api/v1/conversations/{conv_id}/attachments/{aid}")
async def staff_view_attachment(
    conv_id: int, aid: int, staff: dict[str, Any] = Depends(require_staff)
) -> RedirectResponse:
    row = await att_dao.get_attachment(aid)
    if not row or row["conversation_id"] != conv_id:
        raise HTTPException(404, "not found")
    url = await get_object_store().presigned_get(
        row["object_key"], settings.attachment_url_ttl_seconds
    )
    return RedirectResponse(url)
