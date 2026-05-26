# 聊天双向图片（截图）支持 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 C 端 / B 端用户与客服在聊天中双向发送图片（截图），用户发的图传给 `claude-sonnet-4-6` 做 vision 识别，客服侧全程可见。

**Architecture:** 图片存 S3 兼容对象存储（dev=MinIO），DB 新增 `attachments` 表只存元数据（object key），`messages.content` 保持纯文本。上传走 multipart 拿 id，发送时带 `attachment_ids` 绑定到消息行；AI 轮从对象存储读出转 base64 注入 LLM；看图走鉴权端点 302 到短时效预签名 URL（多实例安全）。

**Tech Stack:** FastAPI + SQLAlchemy Core + aioboto3 + Anthropic SDK（后端）；React + TypeScript + Vite（前端）；MinIO（dev 对象存储）。

设计依据：`docs/superpowers/specs/2026-05-26-chat-image-attachments-design.md`

---

## File Structure

**后端新增：**
- `server/src/ai_engine/storage/__init__.py` — 模块标记
- `server/src/ai_engine/storage/object_store.py` — `ObjectStore` 协议 + `S3ObjectStore` 实现 + `get_object_store()` 单例（测试可替换）
- `server/src/ai_engine/persistence/attachments.py` — attachments DAO
- `server/src/ai_engine/api/attachments.py` — 用户侧上传/看图端点 + 共用校验 helper
- `server/tests/test_object_store.py`、`test_attachments_dao.py`、`test_attachments_api.py`、`test_chat_attachments.py`、`test_runtime_vision.py`、`test_staff_attachments.py`

**后端修改：**
- `server/src/ai_engine/config.py` — 新增对象存储配置
- `server/src/ai_engine/persistence/schema.py` — 新增 `attachments` Table
- `server/src/ai_engine/api/chat.py` — `GET /api/v1/chat` 加 `attachment_ids`，绑定
- `server/src/ai_engine/agent/runtime.py` — `run_turn` 注入图片块；`_load_history`/`_coalesce` 支持 list content；纯图片跳过话题分类
- `server/src/ai_engine/api/staff_conversations.py` — 客服上传端点、`StaffMsgIn` 加 `attachment_ids`、`send_message` 绑定、`_human_message_event` 带 attachments、staff 看图端点
- `server/src/ai_engine/main.py` — 注册 attachments router
- `server/pyproject.toml` — 加 `aioboto3` 依赖
- `docker-compose.yml`、`.env` — MinIO 服务 + 配置

**前端新增：**
- `web/src/api/attachments.ts` — `uploadAttachment` / `uploadStaffAttachment` / `attachmentUrl`
- `web/src/components/AttachButton.tsx` — 共用选图+待发缩略图组件
- `web/src/components/ImageThumb.tsx` — 消息内图片缩略图 + 点击放大

**前端修改：**
- `web/src/types.ts` — `Message` / `ChatEvent` 加 `attachments`
- `web/src/api/chat.ts` — `streamChat` 加 `attachmentIds`
- `web/src/api/staff.ts` — `sendStaffMessage` 加 `attachmentIds`
- `web/src/hooks/useChat.ts` — `send(text, attachmentIds?)`
- `web/src/hooks/chatEvents.ts` — `applyEvent`/`applyUserStreamEvent` 透传 attachments
- `web/src/components/InputBox.tsx`、`TakeoverFooter.tsx` — 接入 AttachButton
- `web/src/components/MessageBubble.tsx` — 渲染 attachments
- `web/src/routes/staff/ConversationDetailRoute.tsx`、`ConversationLogsRoute.tsx`、`SpectateRoute.tsx` — 渲染 attachments

---

## Phase A — 后端存储与数据层

### Task 1: 加 aioboto3 依赖 + 对象存储配置

**Files:**
- Modify: `server/pyproject.toml`（dependencies 加 `aioboto3>=13`）
- Modify: `server/src/ai_engine/config.py`
- Modify: `server/.env`（dev 值）

- [ ] **Step 1: 加依赖并安装**

在 `server/pyproject.toml` 的 `dependencies` 列表加一行 `"aioboto3>=13",`。

Run: `cd server && uv pip install -e .`（或项目惯用安装命令）
Expected: 安装成功，`aioboto3` 可 import。

- [ ] **Step 2: config 加对象存储字段**

`server/src/ai_engine/config.py` 的 `Settings` 类里追加（紧跟其他字段）：

```python
    object_store_endpoint: str = "http://localhost:9000"  # MinIO/OSS S3 兼容端点
    object_store_bucket: str = "cs-attachments"
    object_store_access_key: str = ""
    object_store_secret_key: str = ""
    object_store_region: str = "us-east-1"  # MinIO 任意值即可
    attachment_max_bytes: int = 5 * 1024 * 1024  # 单图 5MB
    attachment_max_per_message: int = 4
    attachment_url_ttl_seconds: int = 300  # 预签名 URL 时效
```

- [ ] **Step 3: .env 加 dev 值**

`server/.env` 追加：

```
OBJECT_STORE_ENDPOINT=http://minio:9000
OBJECT_STORE_BUCKET=cs-attachments
OBJECT_STORE_ACCESS_KEY=minioadmin
OBJECT_STORE_SECRET_KEY=minioadmin
```

- [ ] **Step 4: Commit**

```bash
git add server/pyproject.toml server/src/ai_engine/config.py server/.env
git commit -m "chore: 对象存储依赖与配置(aioboto3 + S3兼容)"
```

---

### Task 2: ObjectStore 抽象 + S3 实现 + 单例

**Files:**
- Create: `server/src/ai_engine/storage/__init__.py`（空文件）
- Create: `server/src/ai_engine/storage/object_store.py`
- Test: `server/tests/test_object_store.py`

- [ ] **Step 1: 写失败测试（用 fake store 验证契约 + 单例可替换）**

`server/tests/test_object_store.py`:

```python
import pytest

from ai_engine.storage import object_store as om


class FakeStore:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.data[key] = data

    async def get(self, key: str) -> bytes:
        return self.data[key]

    async def presigned_get(self, key: str, ttl_seconds: int) -> str:
        return f"https://signed.example/{key}?ttl={ttl_seconds}"


@pytest.mark.asyncio
async def test_set_and_get_object_store_singleton():
    fake = FakeStore()
    om.set_object_store(fake)
    assert om.get_object_store() is fake
    await om.get_object_store().put("k", b"abc", "image/png")
    assert await om.get_object_store().get("k") == b"abc"
    url = await om.get_object_store().presigned_get("k", 300)
    assert "ttl=300" in url
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd server && pytest tests/test_object_store.py -v`
Expected: FAIL，`module 'object_store' has no attribute 'set_object_store'`。

- [ ] **Step 3: 实现 object_store.py**

```python
"""S3 兼容对象存储抽象。dev 用 MinIO，生产用 OSS(S3兼容)/S3。

看图走 presigned_get（浏览器直连，多实例无需共享盘）；
发 LLM 走 get → base64（敏感图不交公网 URL，口径统一）。
"""

from typing import Protocol

import aioboto3

from ai_engine.config import settings


class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def presigned_get(self, key: str, ttl_seconds: int) -> str: ...


class S3ObjectStore:
    def __init__(self) -> None:
        self._session = aioboto3.Session()

    def _client(self):
        return self._session.client(
            "s3",
            endpoint_url=settings.object_store_endpoint,
            aws_access_key_id=settings.object_store_access_key,
            aws_secret_access_key=settings.object_store_secret_key,
            region_name=settings.object_store_region,
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        async with self._client() as c:
            await c.put_object(
                Bucket=settings.object_store_bucket, Key=key, Body=data, ContentType=content_type
            )

    async def get(self, key: str) -> bytes:
        async with self._client() as c:
            resp = await c.get_object(Bucket=settings.object_store_bucket, Key=key)
            async with resp["Body"] as body:
                return await body.read()

    async def presigned_get(self, key: str, ttl_seconds: int) -> str:
        async with self._client() as c:
            return await c.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.object_store_bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )


_store: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    global _store
    if _store is None:
        _store = S3ObjectStore()
    return _store


def set_object_store(store: ObjectStore) -> None:
    """测试替换用。"""
    global _store
    _store = store
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd server && pytest tests/test_object_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/storage server/tests/test_object_store.py
git commit -m "feat: ObjectStore S3兼容抽象 + 可替换单例"
```

---

### Task 3: attachments 表 + DAO

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: `server/src/ai_engine/persistence/attachments.py`
- Test: `server/tests/test_attachments_dao.py`

- [ ] **Step 1: schema 加 attachments 表**

`server/src/ai_engine/persistence/schema.py`，在 `staff` 表定义之前或之后追加：

```python
attachments = Table(
    "attachments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, ForeignKey("conversations.id"), nullable=False),
    Column("message_id", Integer, ForeignKey("messages.id")),  # 上传时 NULL，发送绑定后写入
    Column("uploader_type", String(8), nullable=False),  # c / b / staff
    Column("uploader_id", String(128), nullable=False),
    Column("object_key", Text, nullable=False),
    Column("mime", String(64), nullable=False),
    Column("byte_size", Integer, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("created_at", String(32), nullable=False),
)
Index("idx_att_conv", attachments.c.conversation_id)
Index("idx_att_msg", attachments.c.message_id)
```

- [ ] **Step 2: 写失败测试**

`server/tests/test_attachments_dao.py`:

```python
import pytest

from ai_engine.persistence import attachments as att
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence.db import init_db


@pytest.mark.asyncio
async def test_create_bind_and_list():
    await init_db()
    cid = await conv_dao.create_conversation("c", "u-1")
    aid = await att.create_attachment(cid, "c", "u-1", "uploads/x.png", "image/png", 10, "deadbeef")
    assert isinstance(aid, int)

    mid = await conv_dao.append_user_turn(cid, "看这张图", None)
    bound = await att.bind_attachments(mid, cid, "u-1", [aid])
    assert [b["id"] for b in bound] == [aid]

    listed = await att.list_message_attachments(mid)
    assert listed[0]["object_key"] == "uploads/x.png"


@pytest.mark.asyncio
async def test_bind_rejects_cross_conversation_and_double_bind():
    await init_db()
    cid = await conv_dao.create_conversation("c", "u-1")
    other = await conv_dao.create_conversation("c", "u-2")
    aid = await att.create_attachment(cid, "c", "u-1", "uploads/y.png", "image/png", 10, "ab")
    mid = await conv_dao.append_user_turn(cid, "x", None)

    # 别的会话/别的上传者绑不动
    assert await att.bind_attachments(mid, other, "u-1", [aid]) == []
    assert await att.bind_attachments(mid, cid, "u-2", [aid]) == []
    # 正确绑定一次成功
    assert len(await att.bind_attachments(mid, cid, "u-1", [aid])) == 1
    # 已绑定再绑无效（message_id 已非 NULL）
    mid2 = await conv_dao.append_user_turn(cid, "x2", None)
    assert await att.bind_attachments(mid2, cid, "u-1", [aid]) == []
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd server && pytest tests/test_attachments_dao.py -v`
Expected: FAIL，`No module named 'ai_engine.persistence.attachments'`。

- [ ] **Step 4: 实现 attachments.py**

```python
"""attachments DAO：上传时建行(message_id NULL)，发送时按归属+未绑定原子绑定。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_attachment(
    conv_id: int,
    uploader_type: str,
    uploader_id: str,
    object_key: str,
    mime: str,
    byte_size: int,
    sha256: str,
) -> int:
    return await db.insert_returning_id(
        "INSERT INTO attachments"
        "(conversation_id, uploader_type, uploader_id, object_key, mime, byte_size, sha256, "
        "created_at) VALUES (:cid, :ut, :uid, :key, :mime, :sz, :sha, :now) RETURNING id",
        {
            "cid": conv_id, "ut": uploader_type, "uid": uploader_id, "key": object_key,
            "mime": mime, "sz": byte_size, "sha": sha256, "now": now_str(),
        },
    )


async def bind_attachments(
    message_id: int, conv_id: int, uploader_id: str, attachment_ids: list[int]
) -> list[dict[str, Any]]:
    """把未绑定且归属匹配的附件绑到 message_id。逐条 UPDATE ... WHERE message_id IS NULL
    保证幂等/防重复绑定；返回成功绑定的行。"""
    bound: list[dict[str, Any]] = []
    for aid in attachment_ids:
        await db.execute(
            "UPDATE attachments SET message_id=:mid WHERE id=:aid AND conversation_id=:cid "
            "AND uploader_id=:uid AND message_id IS NULL",
            {"mid": message_id, "aid": aid, "cid": conv_id, "uid": uploader_id},
        )
        row = await db.fetch_one(
            "SELECT id, object_key, mime, byte_size FROM attachments "
            "WHERE id=:aid AND message_id=:mid",
            {"aid": aid, "mid": message_id},
        )
        if row:
            bound.append(row)
    return bound


async def list_message_attachments(message_id: int) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, object_key, mime, byte_size FROM attachments "
        "WHERE message_id=:mid ORDER BY id",
        {"mid": message_id},
    )


async def get_attachment(attachment_id: int) -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT id, conversation_id, object_key, mime FROM attachments WHERE id=:aid",
        {"aid": attachment_id},
    )


async def list_for_conversation(conv_id: int) -> dict[int, list[dict[str, Any]]]:
    """客服历史/日志批量取：message_id -> [attachment...]。未绑定(NULL)的跳过。"""
    rows = await db.fetch_all(
        "SELECT id, message_id, mime FROM attachments "
        "WHERE conversation_id=:cid AND message_id IS NOT NULL ORDER BY id",
        {"cid": conv_id},
    )
    out: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(int(r["message_id"]), []).append({"id": r["id"], "mime": r["mime"]})
    return out
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd server && pytest tests/test_attachments_dao.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/persistence/schema.py server/src/ai_engine/persistence/attachments.py server/tests/test_attachments_dao.py
git commit -m "feat: attachments 表 + DAO(建行/归属绑定/批量取)"
```

---

## Phase B — 后端上传与看图端点

### Task 4: 上传校验 helper

**Files:**
- Create: `server/src/ai_engine/api/attachments.py`（先放校验 helper）
- Test: `server/tests/test_attachments_api.py`（先测 helper）

- [ ] **Step 1: 写失败测试**

`server/tests/test_attachments_api.py`:

```python
import pytest

from ai_engine.api import attachments as ah

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


def test_sniff_accepts_png_jpeg():
    assert ah.sniff_image_mime(PNG) == "image/png"
    assert ah.sniff_image_mime(JPEG) == "image/jpeg"


def test_sniff_rejects_non_image():
    assert ah.sniff_image_mime(b"%PDF-1.4 not an image") is None


def test_validate_size_over_limit():
    with pytest.raises(ah.AttachmentTooLarge):
        ah.validate_size(b"x" * (5 * 1024 * 1024 + 1))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd server && pytest tests/test_attachments_api.py -v`
Expected: FAIL，`No module named 'ai_engine.api.attachments'`。

- [ ] **Step 3: 实现 helper（端点 Task 5 再加）**

`server/src/ai_engine/api/attachments.py`:

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd server && pytest tests/test_attachments_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/api/attachments.py server/tests/test_attachments_api.py
git commit -m "feat: 上传校验 helper(magic-byte嗅探/大小/objectkey)"
```

---

### Task 5: 用户侧上传 + 看图端点

**Files:**
- Modify: `server/src/ai_engine/api/attachments.py`
- Modify: `server/src/ai_engine/main.py`（注册 router）
- Test: `server/tests/test_attachments_api.py`（加端点测试）

- [ ] **Step 1: 写失败测试（上传 + 看图 302）**

在 `server/tests/test_attachments_api.py` 追加。复用现有测试里构造 app/client 与 C 端鉴权的方式（参考 `server/tests/test_chat_api.py` 如何建 `httpx.AsyncClient` 与注入身份 / `set_object_store`）：

```python
from ai_engine.storage import object_store as om


class _FakeStore:
    def __init__(self):
        self.data = {}

    async def put(self, key, data, content_type):
        self.data[key] = data

    async def get(self, key):
        return self.data[key]

    async def presigned_get(self, key, ttl_seconds):
        return f"https://signed.example/{key}"


@pytest.mark.asyncio
async def test_user_upload_and_view(client_c, conv_id_c):
    om.set_object_store(_FakeStore())
    files = {"file": ("s.png", PNG, "image/png")}
    r = await client_c.post(f"/api/v1/conversations/{conv_id_c}/attachments", files=files)
    assert r.status_code == 200
    aid = r.json()["attachment_id"]

    # 看图端点：鉴权后 302 到预签名 URL（不跟随重定向）
    r2 = await client_c.get(
        f"/api/v1/conversations/{conv_id_c}/attachments/{aid}", follow_redirects=False
    )
    assert r2.status_code == 307 or r2.status_code == 302
    assert "signed.example" in r2.headers["location"]


@pytest.mark.asyncio
async def test_user_upload_rejects_non_image(client_c, conv_id_c):
    om.set_object_store(_FakeStore())
    files = {"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}
    r = await client_c.post(f"/api/v1/conversations/{conv_id_c}/attachments", files=files)
    assert r.status_code == 415
```

> 注：`client_c` / `conv_id_c` fixture 若不存在，按 `test_chat_api.py` 同款模式新建（解析 C 端身份 + 建会话）。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd server && pytest tests/test_attachments_api.py -k upload -v`
Expected: FAIL（404，端点未注册）。

- [ ] **Step 3: 实现端点**

在 `server/src/ai_engine/api/attachments.py` 顶部补 import 并追加端点。鉴权复用 chat.py 同款 `_authorize_conversation`（直接 import 或抽到公共处；这里直接 import）：

```python
from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from ai_engine.api.chat import _authorize_conversation
from ai_engine.persistence import attachments as att_dao
from ai_engine.storage.object_store import get_object_store


async def _store_upload(conv_id: int, uploader_type: str, uploader_id: str, file: UploadFile):
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
    user_type, subject_id = await _authorize_conversation(request, conv_id)
    try:
        aid = await _store_upload(conv_id, user_type, subject_id, file)
    except AttachmentTooLarge:
        raise HTTPException(413, "image too large")
    except AttachmentBadType:
        raise HTTPException(415, "unsupported image type")
    return {"attachment_id": aid}


@router.get("/api/v1/conversations/{conv_id}/attachments/{aid}")
async def view_attachment(conv_id: int, aid: int, request: Request) -> RedirectResponse:
    await _authorize_conversation(request, conv_id)
    row = await att_dao.get_attachment(aid)
    if not row or row["conversation_id"] != conv_id:
        raise HTTPException(404, "not found")
    url = await get_object_store().presigned_get(row["object_key"], settings.attachment_url_ttl_seconds)
    return RedirectResponse(url)
```

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.attachments import router as attachments_router` 并在其他 `include_router` 旁加 `app.include_router(attachments_router)`。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd server && pytest tests/test_attachments_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/attachments.py server/src/ai_engine/main.py server/tests/test_attachments_api.py
git commit -m "feat: 用户侧图片上传 + 鉴权看图(302预签名)端点"
```

---

## Phase C — 后端发送绑定与 LLM 注入

### Task 6: chat 端点接收 attachment_ids 并绑定

**Files:**
- Modify: `server/src/ai_engine/api/chat.py`
- Modify: `server/src/ai_engine/agent/runtime.py:202`（`run_turn` 签名加 `attachment_ids`）
- Test: `server/tests/test_chat_attachments.py`

- [ ] **Step 1: 写失败测试（带 attachment_ids 发送后附件被绑定到 user 行）**

`server/tests/test_chat_attachments.py`:

```python
import pytest

from ai_engine.persistence import attachments as att_dao
from ai_engine.persistence import conversations as conv_dao
from ai_engine.storage import object_store as om
from tests.helpers import fake_anthropic_stream  # 若已有；否则按 test_chat_api 同款 mock


@pytest.mark.asyncio
async def test_chat_binds_attachments_to_user_turn(client_c, conv_id_c, monkeypatch):
    # 预上传一张图（直接建行，object_key 落 fake store）
    aid = await att_dao.create_attachment(conv_id_c, "c", "u-1", "uploads/a.png", "image/png", 10, "ab")
    # 走 chat（mock LLM，详见 test_chat_api 的 stream patch）
    resp = await client_c.get(
        f"/api/v1/chat?conversation_id={conv_id_c}&message=hi&attachment_ids={aid}"
    )
    assert resp.status_code == 200
    # user 行已绑定该附件
    rows = await att_dao.list_for_conversation(conv_id_c)
    assert any(aid == a["id"] for atts in rows.values() for a in atts)
```

> mock LLM 与 client_c/conv_id_c 沿用 `test_chat_api.py` 既有 fixture/patch 方式。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd server && pytest tests/test_chat_attachments.py -v`
Expected: FAIL（attachment_ids 参数未处理，附件 message_id 仍 NULL）。

- [ ] **Step 3: chat.py 加参数 + 透传**

`server/src/ai_engine/api/chat.py`：
1. `chat()` 签名加 `attachment_ids: str | None = Query(default=None)`。
2. 解析为 list：在 `gen()` 内进入 `_stream_ai_turn` / human 分支前算 `att_ids = [int(x) for x in attachment_ids.split(",") if x.strip().isdigit()][: ...]`（数量上限用 `settings.attachment_max_per_message`）。
3. 把 `att_ids` 透传给 `_stream_ai_turn(...)` 与 human 模式下的 `append_message` 后绑定。

`_stream_ai_turn` 签名加 `attachment_ids: list[int]`，并透传给 `runtime.run_turn(..., attachment_ids=attachment_ids)`。

human 模式分支（`chat.py` 现 170-175 行）改为：

```python
mid = await conv_dao.append_message(conversation_id, role="user", content=message)
if attachment_ids:
    from ai_engine.persistence import attachments as att_dao
    await att_dao.bind_attachments(mid, conversation_id, subject_id, attachment_ids)
publish_user_message(conversation_id, message)  # Task 8 再带 attachments
```

> `append_message` 当前返回 id（见 DAO），直接用其返回值。

- [ ] **Step 4: runtime.run_turn 绑定附件到 turn 行**

`server/src/ai_engine/agent/runtime.py`，`run_turn` 签名加 `attachment_ids: list[int] | None = None`。在 `turn_id = await append_user_turn(...)`（225-227 行附近）之后加：

```python
    bound_atts: list[dict[str, Any]] = []
    if attachment_ids:
        from ai_engine.persistence import attachments as att_dao
        bound_atts = await att_dao.bind_attachments(turn_id, conversation_id, subject_id, attachment_ids)
```

（`bound_atts` 在 Task 7 用于注入；本任务先完成绑定。）

- [ ] **Step 5: 运行测试确认通过**

Run: `cd server && pytest tests/test_chat_attachments.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/chat.py server/src/ai_engine/agent/runtime.py server/tests/test_chat_attachments.py
git commit -m "feat: chat 端点接收 attachment_ids 并绑定到 user 回合"
```

---

### Task 7: LLM 注入图片块 + 历史/coalesce 支持 list content + 纯图片跳过分类

**Files:**
- Modify: `server/src/ai_engine/agent/runtime.py`（`run_turn` 注入、`_coalesce`、`_load_history`、话题分类分支）
- Test: `server/tests/test_runtime_vision.py`

- [ ] **Step 1: 写失败测试（本轮带图 → 发给 LLM 的 user content 是 image+text 块；纯图片不跑分类）**

`server/tests/test_runtime_vision.py`:

```python
import base64

import pytest

from ai_engine.agent import runtime
from ai_engine.persistence import attachments as att_dao
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence.db import init_db
from ai_engine.storage import object_store as om


class _FakeStore:
    async def put(self, k, d, c): ...
    async def get(self, key):
        return b"IMGBYTES"
    async def presigned_get(self, k, t):
        return "x"


@pytest.mark.asyncio
async def test_build_user_content_with_image_block():
    om.set_object_store(_FakeStore())
    atts = [{"id": 1, "object_key": "uploads/a.png", "mime": "image/png"}]
    content = await runtime._build_user_content("看这张", atts)
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["data"] == base64.b64encode(b"IMGBYTES").decode()
    assert content[-1] == {"type": "text", "text": "看这张"}


def test_coalesce_does_not_merge_list_content():
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "a"}]},
        {"role": "user", "content": "b"},
    ]
    out = runtime._coalesce(msgs)
    # list content 不做字符串拼接，保持独立两条
    assert len(out) == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd server && pytest tests/test_runtime_vision.py -v`
Expected: FAIL（`_build_user_content` 不存在；`_coalesce` 对 list 会抛 `can only concatenate list`）。

- [ ] **Step 3: 实现注入 + 修 coalesce/history**

`server/src/ai_engine/agent/runtime.py`：

新增 helper（放在 `_history_text` 附近）：

```python
import base64

from ai_engine.storage.object_store import get_object_store


async def _build_user_content(text: str, attachments: list[dict[str, Any]]) -> Any:
    """有附件时返回 [image..., text] 内容块；无附件返回纯文本 str。"""
    if not attachments:
        return text
    blocks: list[dict[str, Any]] = []
    store = get_object_store()
    for a in attachments:
        raw = await store.get(a["object_key"])
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": a["mime"],
                    "data": base64.b64encode(raw).decode(),
                },
            }
        )
    if text:
        blocks.append({"type": "text", "text": text})
    return blocks
```

改 `_coalesce`（157-165 行）：相邻同 role 只在两边都是 str 时才拼接，否则各自独立：

```python
def _coalesce(msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in msgs:
        if (
            out
            and out[-1]["role"] == m["role"]
            and isinstance(out[-1]["content"], str)
            and isinstance(m["content"], str)
        ):
            out[-1]["content"] += "\n" + m["content"]
        else:
            out.append(dict(m))
    return out
```

改 `run_turn`：把 `messages.append({"role": "user", "content": user_message})`（225 行）改为在 `bound_atts` 就绪后注入。注意顺序——`append_user_turn` 和 `bind_attachments`（Task 6 加的）需在构造 LLM content 之前。调整为：

```python
    turn_id = await append_user_turn(conversation_id, user_message, client_message_id)
    bound_atts: list[dict[str, Any]] = []
    if attachment_ids:
        from ai_engine.persistence import attachments as att_dao
        bound_atts = await att_dao.bind_attachments(
            turn_id, conversation_id, subject_id, attachment_ids
        )
    messages.append({"role": "user", "content": await _build_user_content(user_message, bound_atts)})
```

（删除原先单独的 `messages.append({"role": "user", "content": user_message})` 行，避免重复 append。）

纯图片跳过话题分类：话题分类分支（234-248 行）外层包一个判断——`user_message` 为空（纯图片）时跳过分类，视为放行：

```python
    if settings.topic_classifier_enabled and user_message.strip():
        ...原分类逻辑...
```

- [ ] **Step 4: 历史回放注入图片（_load_history）**

改 `_load_history`（168-181 行）：user 行若有绑定附件，content 走 `_build_user_content`。因 `_load_history` 现为同步遍历，改为对 user 行查附件并 await：

```python
async def _load_history(conv_id: int) -> list[dict[str, Any]]:
    from ai_engine.persistence import attachments as att_dao
    att_map = await att_dao.list_for_conversation(conv_id)  # message_id -> [{id, mime}]
    msgs: list[dict[str, Any]] = []
    for m in await list_messages(conv_id):
        role = str(m["role"])
        content = str(m["content"])
        if role == "user":
            atts = await att_dao.list_message_attachments(int(m["id"])) if int(m["id"]) in att_map else []
            msgs.append({"role": "user", "content": await _build_user_content(content, atts)})
        elif role in ("assistant", "human_agent"):
            text = _history_text(role, content)
            if text:
                msgs.append({"role": "assistant", "content": text})
    return _coalesce(msgs)
```

- [ ] **Step 5: 运行测试确认通过 + 回归**

Run: `cd server && pytest tests/test_runtime_vision.py tests/test_chat_attachments.py -v`
Expected: PASS
Run: `cd server && pytest tests/test_chat_api.py tests/test_anthropic_client.py -v`
Expected: PASS（确认未破坏既有纯文本路径）

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/agent/runtime.py server/tests/test_runtime_vision.py
git commit -m "feat: run_turn 注入图片base64块 + 历史回放带图 + 纯图片跳过分类"
```

---

### Task 8: 客服侧上传 + 发图 + 事件带 attachments

**Files:**
- Modify: `server/src/ai_engine/api/attachments.py`（客服上传/看图端点）
- Modify: `server/src/ai_engine/api/staff_conversations.py`（`StaffMsgIn`、`send_message`、`_human_message_event`、`publish_user_message`）
- Modify: `server/src/ai_engine/api/chat.py`（human 模式 publish 带 attachments — 见 Task 6 留的 TODO）
- Test: `server/tests/test_staff_attachments.py`

- [ ] **Step 1: 写失败测试**

`server/tests/test_staff_attachments.py`:

```python
import pytest

from ai_engine.persistence import attachments as att_dao
from ai_engine.storage import object_store as om

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.mark.asyncio
async def test_staff_upload_and_send_with_attachment(staff_client, taken_conv_id):
    om.set_object_store(_FakeStore())
    files = {"file": ("s.png", PNG, "image/png")}
    r = await staff_client.post(f"/staff/api/v1/conversations/{taken_conv_id}/attachments", files=files)
    assert r.status_code == 200
    aid = r.json()["attachment_id"]

    r2 = await staff_client.post(
        f"/staff/api/v1/conversations/{taken_conv_id}/messages",
        json={"content": "给你截图", "attachment_ids": [aid]},
    )
    assert r2.status_code == 200
    rows = await att_dao.list_for_conversation(taken_conv_id)
    assert any(aid == a["id"] for atts in rows.values() for a in atts)


class _FakeStore:
    async def put(self, k, d, c): ...
    async def get(self, k):
        return b"x"
    async def presigned_get(self, k, t):
        return "https://signed.example/x"
```

> `staff_client` / `taken_conv_id`（已 take 的会话）沿用 `test_staff_ai_tools.py` / `test_chat_human_mode.py` 既有 fixture。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd server && pytest tests/test_staff_attachments.py -v`
Expected: FAIL（客服上传端点 404；`StaffMsgIn` 无 `attachment_ids`）。

- [ ] **Step 3: 客服上传/看图端点**

`server/src/ai_engine/api/attachments.py` 追加（鉴权用 `require_staff` + 担当校验，参考 staff_conversations 的 `_require_assigned`）：

```python
from ai_engine.auth.staff_auth import require_staff  # 按实际 require_staff 所在模块调整 import
from ai_engine.persistence import conversations as conv_dao


async def _assert_staff_conv(conv_id: int, staff_sub: str) -> None:
    mode, sid = await conv_dao.get_mode(conv_id)
    if mode != "human_takeover" or sid != staff_sub:
        raise HTTPException(403, "not your conversation")


@router.post("/staff/api/v1/conversations/{conv_id}/attachments")
async def staff_upload_attachment(
    conv_id: int, file: UploadFile = File(...), staff=Depends(require_staff)
) -> dict[str, int]:
    await _assert_staff_conv(conv_id, staff["sub"])
    try:
        aid = await _store_upload(conv_id, "staff", staff["sub"], file)
    except AttachmentTooLarge:
        raise HTTPException(413, "image too large")
    except AttachmentBadType:
        raise HTTPException(415, "unsupported image type")
    return {"attachment_id": aid}


@router.get("/staff/api/v1/conversations/{conv_id}/attachments/{aid}")
async def staff_view_attachment(conv_id: int, aid: int, staff=Depends(require_staff)) -> RedirectResponse:
    row = await att_dao.get_attachment(aid)
    if not row or row["conversation_id"] != conv_id:
        raise HTTPException(404, "not found")
    url = await get_object_store().presigned_get(row["object_key"], settings.attachment_url_ttl_seconds)
    return RedirectResponse(url)
```

> import `Depends` from fastapi；`require_staff` 的真实导入路径以 `staff_conversations.py` 顶部为准。

- [ ] **Step 4: StaffMsgIn + send_message 绑定 + 事件带 attachments**

`server/src/ai_engine/api/staff_conversations.py`：

`StaffMsgIn`（244 行）加字段：

```python
class StaffMsgIn(BaseModel):
    content: str = ""
    attachment_ids: list[int] = []
```

`send_message`（249-257 行）改：允许"文本非空或有附件"，绑定后事件带 attachments：

```python
    if not body.content.strip() and not body.attachment_ids:
        raise HTTPException(422, "empty message")
    mid = await conv_dao.append_human_message(conv_id, staff["sub"], body.content)
    from ai_engine.persistence import attachments as att_dao
    bound = await att_dao.bind_attachments(mid, conv_id, staff["sub"], body.attachment_ids)
    _publish(conv_id, await _human_message_event(staff["sub"], body.content, bound))
    return {"ok": True}
```

`_human_message_event`（114-123 行）加 `attachments` 参数：

```python
async def _human_message_event(
    staff_sub: str, content: str, attachments: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    staff = await get_staff(staff_sub)
    display_name = staff["display_name"] if staff else staff_sub
    return {
        "type": "human_message",
        "content": content,
        "sender_staff_id": staff_sub,
        "display_name": display_name,
        "attachments": [{"id": a["id"], "mime": a["mime"]} for a in (attachments or [])],
    }
```

`publish_user_message`（126-128 行）加 attachments：

```python
def publish_user_message(conv_id: int, content: str, attachments: list[dict[str, Any]] | None = None) -> None:
    _publish(conv_id, {
        "type": "user_message",
        "content": content,
        "attachments": [{"id": a["id"], "mime": a["mime"]} for a in (attachments or [])],
    })
```

- [ ] **Step 5: chat.py human 模式 publish 带 attachments**

`server/src/ai_engine/api/chat.py` human 分支（Task 6 Step 3 留的）改为：

```python
    mid = await conv_dao.append_message(conversation_id, role="user", content=message)
    from ai_engine.persistence import attachments as att_dao
    bound = await att_dao.bind_attachments(mid, conversation_id, subject_id, attachment_ids) if attachment_ids else []
    publish_user_message(conversation_id, message, bound)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd server && pytest tests/test_staff_attachments.py tests/test_chat_human_mode.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add server/src/ai_engine/api/attachments.py server/src/ai_engine/api/staff_conversations.py server/src/ai_engine/api/chat.py server/tests/test_staff_attachments.py
git commit -m "feat: 客服侧上传/发图 + user/human_message 事件携带 attachments"
```

---

## Phase D — 前端

### Task 9: 前端类型 + 上传 API client

**Files:**
- Modify: `web/src/types.ts`
- Create: `web/src/api/attachments.ts`
- Modify: `web/src/api/chat.ts`、`web/src/api/staff.ts`
- Test: `web/tests/attachments.test.ts`

- [ ] **Step 1: 写失败测试**

`web/tests/attachments.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { attachmentUrl, staffAttachmentUrl } from "../src/api/attachments";

describe("attachmentUrl", () => {
  it("builds user view url", () => {
    expect(attachmentUrl(12, 5)).toBe("/api/v1/conversations/12/attachments/5");
  });
  it("builds staff view url", () => {
    expect(staffAttachmentUrl(12, 5)).toBe("/staff/api/v1/conversations/12/attachments/5");
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd web && pnpm vitest run tests/attachments.test.ts`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: types.ts 加 attachments**

`web/src/types.ts`：定义并接入

```ts
export type Attachment = { id: number; mime: string };
```

`Message` 的 user/assistant/human_agent 变体各加 `attachments?: Attachment[]`：

```ts
export type Message =
  | { role: "system"; content: string }
  | { role: "user"; content: string; attachments?: Attachment[] }
  | { role: "assistant"; content: string; tool_calls?: ToolCallShown[]; attachments?: Attachment[] }
  | { role: "human_agent"; content: string; display_name?: string; attachments?: Attachment[] };
```

`ChatEvent` 的 `human_message` 变体（约 19 行）与 `user_message`/`assistant_message` 处加 `attachments?: Attachment[]`。

- [ ] **Step 4: 实现 api/attachments.ts**

```ts
import { authHeaders } from "./identity";

async function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const auth = await authHeaders();
  return fetch(input, { ...init, credentials: "include", headers: { ...(init.headers ?? {}), ...auth } });
}

export function attachmentUrl(conversationId: number, attachmentId: number): string {
  return `/api/v1/conversations/${conversationId}/attachments/${attachmentId}`;
}

export function staffAttachmentUrl(conversationId: number, attachmentId: number): string {
  return `/staff/api/v1/conversations/${conversationId}/attachments/${attachmentId}`;
}

/** 上传单张图，返回 attachment_id。 */
export async function uploadAttachment(conversationId: number, file: File): Promise<number> {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await authedFetch(`/api/v1/conversations/${conversationId}/attachments`, {
    method: "POST",
    body: fd,
  });
  if (!resp.ok) throw new Error(`upload http ${resp.status}`);
  return (await resp.json()).attachment_id;
}

export async function uploadStaffAttachment(conversationId: number, file: File, token: string): Promise<number> {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await fetch(`/staff/api/v1/conversations/${conversationId}/attachments`, {
    method: "POST",
    credentials: "include",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  if (!resp.ok) throw new Error(`staff upload http ${resp.status}`);
  return (await resp.json()).attachment_id;
}
```

> staff 鉴权头以 `web/src/api/staff.ts` 既有方式为准（若 staff 用 cookie 而非 Bearer，去掉 Authorization、保留 credentials）。

- [ ] **Step 5: chat.ts / staff.ts 加 attachmentIds**

`web/src/api/chat.ts` 的 `streamChat`（47-64 行）：args 加 `attachmentIds?: number[]`，拼 URL 时若非空加 `&attachment_ids=1,2`：

```ts
  if (args.attachmentIds?.length) url += `&attachment_ids=${args.attachmentIds.join(",")}`;
```

`web/src/api/staff.ts` 的 `sendStaffMessage`：body 加 `attachment_ids`：

```ts
export async function sendStaffMessage(token: string, convId: number, content: string, attachmentIds: number[] = []) {
  // ...既有 fetch，body 改为 JSON.stringify({ content, attachment_ids: attachmentIds })
}
```

- [ ] **Step 6: 运行测试确认通过 + type-check**

Run: `cd web && pnpm vitest run tests/attachments.test.ts && pnpm tsc --noEmit`
Expected: PASS，无类型错误。

- [ ] **Step 7: Commit**

```bash
git add web/src/types.ts web/src/api/attachments.ts web/src/api/chat.ts web/src/api/staff.ts web/tests/attachments.test.ts
git commit -m "feat(web): attachments 类型 + 上传/看图 API client"
```

---

### Task 10: AttachButton 选图组件 + InputBox 接入 + useChat send 扩展

**Files:**
- Create: `web/src/components/AttachButton.tsx`
- Modify: `web/src/components/InputBox.tsx`
- Modify: `web/src/hooks/useChat.ts`（`useChatSend` 的 `send`）、`web/src/components/ChatWindow.tsx`（透传）
- Test: `web/tests/attachButton.test.tsx`

- [ ] **Step 1: 写失败测试**

`web/tests/attachButton.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AttachButton } from "../src/components/AttachButton";

describe("AttachButton", () => {
  it("uploads picked file and reports id", async () => {
    const upload = vi.fn().mockResolvedValue(42);
    const onChange = vi.fn();
    render(<AttachButton upload={upload} ids={[]} onChange={onChange} max={4} />);
    const file = new File([new Uint8Array([1])], "a.png", { type: "image/png" });
    const input = screen.getByTestId("attach-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(onChange).toHaveBeenCalledWith([42]));
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd web && pnpm vitest run tests/attachButton.test.tsx`
Expected: FAIL（组件不存在）。

- [ ] **Step 3: 实现 AttachButton**

`web/src/components/AttachButton.tsx`（受控：父持有已上传 ids + 待发缩略图 URL；组件管选图/上传/删除）：

```tsx
import { ImagePlus, X } from "lucide-react";
import { useRef, useState } from "react";

type Pending = { id: number; url: string };

export function AttachButton({
  upload,
  ids,
  onChange,
  max,
  disabled,
}: {
  upload: (file: File) => Promise<number>;
  ids: number[];
  onChange: (ids: number[]) => void;
  max: number;
  disabled?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<Pending[]>([]);
  const [busy, setBusy] = useState(false);

  async function pick(files: FileList | null) {
    if (!files) return;
    const room = max - ids.length;
    const chosen = Array.from(files).slice(0, room);
    setBusy(true);
    try {
      for (const f of chosen) {
        const id = await upload(f);
        setPending((p) => [...p, { id, url: URL.createObjectURL(f) }]);
        onChange([...ids, id]);
      }
    } finally {
      setBusy(false);
      if (ref.current) ref.current.value = "";
    }
  }

  function remove(id: number) {
    setPending((p) => p.filter((x) => x.id !== id));
    onChange(ids.filter((x) => x !== id));
  }

  return (
    <>
      {pending.length > 0 && (
        <div className="flex gap-2 flex-wrap pb-2">
          {pending.map((p) => (
            <div key={p.id} className="relative">
              <img src={p.url} alt="" className="h-14 w-14 rounded object-cover" />
              <button
                onClick={() => remove(p.id)}
                className="absolute -right-1 -top-1 rounded-full bg-black/60 p-0.5 text-white"
                aria-label="remove"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
      <button
        type="button"
        disabled={disabled || busy || ids.length >= max}
        onClick={() => ref.current?.click()}
        aria-label="attach image"
        className="grid h-10 w-10 place-items-center rounded text-ink-secondary hover:text-ink disabled:opacity-40"
      >
        <ImagePlus className="h-5 w-5" />
      </button>
      <input
        ref={ref}
        data-testid="attach-input"
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => void pick(e.target.files)}
      />
    </>
  );
}
```

- [ ] **Step 4: InputBox 接入**

`web/src/components/InputBox.tsx`：`onSend` 签名改 `(text: string, attachmentIds?: number[]) => void`，加 `upload` prop。内部维护 `ids` state，渲染 `<AttachButton>` 于 textarea 行左侧；`submit()` 改为允许"文本非空或 ids 非空"，发送后清空 ids；支持 paste（`onPaste` 取 `e.clipboardData.files` 走同一上传）。

关键改动：

```tsx
const [ids, setIds] = useState<number[]>([]);
function submit() {
  const text = v.trim();
  if ((text || ids.length) && !disabled) {
    onSend(text, ids);
    setV("");
    setIds([]);
  }
}
// disabled 按钮条件: disabled || (!v.trim() && ids.length === 0)
```

- [ ] **Step 5: useChat.send + ChatWindow 透传**

`web/src/hooks/useChat.ts` 的 `useChatSend.send`（125 行）签名改 `async (text: string, attachmentIds?: number[])`，本地追加 user 行带 attachments（占位用空 mime，渲染时用 id 拼 URL）：

```ts
actions.setMessages((prev) => [
  ...prev,
  { role: "user", content: text, attachments: (attachmentIds ?? []).map((id) => ({ id, mime: "image/*" })) },
]);
```

并把 `attachmentIds` 透传给 `streamChat({ ..., attachmentIds })`。

`web/src/components/ChatWindow.tsx`：`<InputBox onSend={send} upload={(f) => uploadAttachment(init!.conversation_id, f)} ... />`（init 为空时禁用）。

- [ ] **Step 6: 运行测试 + type-check**

Run: `cd web && pnpm vitest run tests/attachButton.test.tsx && pnpm tsc --noEmit`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add web/src/components/AttachButton.tsx web/src/components/InputBox.tsx web/src/hooks/useChat.ts web/src/components/ChatWindow.tsx web/tests/attachButton.test.tsx
git commit -m "feat(web): 用户侧选图上传(AttachButton)接入输入框 + send 带 attachmentIds"
```

---

### Task 11: MessageBubble 渲染图片 + ImageThumb 放大

**Files:**
- Create: `web/src/components/ImageThumb.tsx`
- Modify: `web/src/components/MessageBubble.tsx`
- Modify: `web/src/hooks/chatEvents.ts`（透传 attachments 进 Message）
- Test: `web/tests/messageBubbleImage.test.tsx`

- [ ] **Step 1: 写失败测试**

`web/tests/messageBubbleImage.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImageThumb } from "../src/components/ImageThumb";

describe("ImageThumb", () => {
  it("renders an img with given src", () => {
    render(<ImageThumb src="/api/v1/conversations/1/attachments/5" />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/api/v1/conversations/1/attachments/5");
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd web && pnpm vitest run tests/messageBubbleImage.test.tsx`
Expected: FAIL（组件不存在）。

- [ ] **Step 3: 实现 ImageThumb**

`web/src/components/ImageThumb.tsx`:

```tsx
import { useState } from "react";

export function ImageThumb({ src }: { src: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <img
        src={src}
        alt=""
        onClick={() => setOpen(true)}
        className="max-h-48 max-w-[200px] cursor-zoom-in rounded-md object-cover"
      />
      {open && (
        <div
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-50 grid place-items-center bg-black/80 p-4"
        >
          <img src={src} alt="" className="max-h-full max-w-full rounded" />
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 4: MessageBubble 渲染 attachments**

`web/src/components/MessageBubble.tsx`：在文本气泡内/上方渲染 `m.attachments`。需要 conversationId 才能拼 URL——`MessageBubble` 接受 `conversationId` prop（由 `MessageList`→`ChatWindow` 透传 `init.conversation_id`），staff 侧传对应 id 并用 `staffAttachmentUrl`。

最小实现（用户侧）：

```tsx
{m.attachments?.length ? (
  <div className="flex flex-wrap gap-2 mt-1">
    {m.attachments.map((a) => (
      <ImageThumb key={a.id} src={attachmentUrl(conversationId, a.id)} />
    ))}
  </div>
) : null}
```

> `MessageList`（32-41 行）透传 `conversationId` 给每个 `MessageBubble`；`ChatWindow` 把 `init.conversation_id` 传给 `MessageList`。staff 侧组件传 staff URL builder（可加一个 `urlFor?: (id) => string` prop，默认用 `attachmentUrl`）。

- [ ] **Step 5: chatEvents 透传 attachments**

`web/src/hooks/chatEvents.ts`：
- `applyEvent` 的 `human_message`（14-15 行）→ `{ role: "human_agent", content: ev.content, display_name: ev.display_name, attachments: ev.attachments }`。
- `assistant_message`（16 行）同理带 `attachments`。
- `applyUserStreamEvent` 的 `user_message`（若有）→ push user 行带 attachments。

- [ ] **Step 6: 运行测试 + type-check + 全量前端测试**

Run: `cd web && pnpm vitest run && pnpm tsc --noEmit`
Expected: PASS（含既有 staff/multiStaff 测试不回归）

- [ ] **Step 7: Commit**

```bash
git add web/src/components/ImageThumb.tsx web/src/components/MessageBubble.tsx web/src/components/MessageList.tsx web/src/components/ChatWindow.tsx web/src/hooks/chatEvents.ts web/tests/messageBubbleImage.test.tsx
git commit -m "feat(web): 消息气泡渲染图片缩略图 + 点击放大 + 事件透传 attachments"
```

---

### Task 12: 客服 TakeoverFooter 发图 + 客服控制台渲染

**Files:**
- Modify: `web/src/components/TakeoverFooter.tsx`
- Modify: `web/src/routes/staff/ConversationDetailRoute.tsx`、`ConversationLogsRoute.tsx`、`SpectateRoute.tsx`
- Test: `web/tests/staffAttach.test.tsx`

- [ ] **Step 1: 写失败测试（客服发送带 attachment_ids）**

`web/tests/staffAttach.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TakeoverFooter } from "../src/components/TakeoverFooter";

vi.mock("../src/api/staff", () => ({
  sendStaffMessage: vi.fn().mockResolvedValue(undefined),
  resolveConversation: vi.fn(),
  transferConversation: vi.fn(),
}));
vi.mock("../src/api/attachments", () => ({
  uploadStaffAttachment: vi.fn().mockResolvedValue(7),
  staffAttachmentUrl: (c: number, a: number) => `/staff/api/v1/conversations/${c}/attachments/${a}`,
}));

import { sendStaffMessage } from "../src/api/staff";

describe("TakeoverFooter image send", () => {
  it("sends with attachment ids", async () => {
    render(<TakeoverFooter token="t" convId={3} /* + 既有必填 props */ />);
    const file = new File([new Uint8Array([1])], "a.png", { type: "image/png" });
    fireEvent.change(screen.getByTestId("attach-input"), { target: { files: [file] } });
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "看图" } });
    fireEvent.click(screen.getByText(/发送|Send/));
    await waitFor(() => expect(sendStaffMessage).toHaveBeenCalledWith("t", 3, "看图", [7]));
  });
});
```

> 按 `web/tests/staff.test.tsx` 既有方式补齐 TakeoverFooter 必填 props。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd web && pnpm vitest run tests/staffAttach.test.tsx`
Expected: FAIL（无 attach-input；send 未带 ids）。

- [ ] **Step 3: TakeoverFooter 接入 AttachButton**

`web/src/components/TakeoverFooter.tsx`：维护 `ids` state，渲染 `<AttachButton upload={(f) => uploadStaffAttachment(convId, f, token)} ids={ids} onChange={setIds} max={4} />`；`send()`（20-24 行）改为 `await sendStaffMessage(token, convId, draft.trim(), ids)`，发送后清空 `draft` 与 `ids`；空消息条件改"文本空且无 ids"。

- [ ] **Step 4: 客服控制台渲染 attachments**

三个 staff route 在渲染消息历史/流时透传 attachments 并用 `staffAttachmentUrl`：
- `ConversationDetailRoute.tsx`：拉历史接口需返回 attachments（若 `list_messages` 接口未带，前端调 `list_for_conversation` 等价数据——后端 `get_one` 返回体加 attachments map，见下方注）。给 `MessageBubble` 传 `urlFor={(id) => staffAttachmentUrl(convId, id)}`。
- `ConversationLogsRoute.tsx`：同样渲染。
- `SpectateRoute.tsx`：旁观流 `user_message` 事件带 attachments → 渲染。

> **后端补充**（若 `GET /staff/api/v1/conversations/{id}` 历史不含 attachments）：在该端点返回的每条 message 上合并 `attachments`（调 `att_dao.list_for_conversation`）。这一步若测试发现缺失则补；属本任务范围。

- [ ] **Step 5: 运行测试 + type-check + 全量**

Run: `cd web && pnpm vitest run && pnpm tsc --noEmit`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/src/components/TakeoverFooter.tsx web/src/routes/staff/ web/tests/staffAttach.test.tsx
git commit -m "feat(web): 客服侧发图 + 控制台渲染用户/客服图片"
```

---

## Phase E — 基建接入与端到端

### Task 13: docker-compose 加 MinIO + bucket 初始化

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 加 MinIO 服务 + bucket 创建**

`docker-compose.yml` 加服务（端口、卷与现有风格对齐）：

```yaml
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/data

  minio-init:
    image: minio/mc:latest
    depends_on:
      - minio
    entrypoint: >
      /bin/sh -c "
      until mc alias set local http://minio:9000 minioadmin minioadmin; do sleep 1; done;
      mc mb -p local/cs-attachments || true;
      "
```

并在 `volumes:` 段加 `minio-data:`。`api` 服务的 `depends_on` 加 `minio`。

- [ ] **Step 2: 起服务验证 bucket**

Run: `docker compose up -d minio minio-init && docker compose logs minio-init | tail`
Expected: 看到 bucket `cs-attachments` 创建成功（或已存在）。

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: docker-compose 加 MinIO + cs-attachments bucket 初始化"
```

---

### Task 14: 全量回归 + 端到端验证

**Files:** 无（验证）

- [ ] **Step 1: 后端全量测试**

Run: `cd server && pytest -q`
Expected: 全绿（含新增 5 个测试文件）。

- [ ] **Step 2: 前端全量测试 + 类型 + 构建**

Run: `cd web && pnpm vitest run && pnpm tsc --noEmit && pnpm build`
Expected: 全绿，dist 构建成功。

- [ ] **Step 3: 起全栈手动验证（按 CLAUDE.md：改后端需 rebuild）**

Run: `docker compose up -d --build api minio minio-init web`
Expected: api 启动日志无错误，`/api/v1/conversations/{id}/attachments` 可上传。

- [ ] **Step 4: 端到端冒烟（手动 / 脚本）**

验证三条链路：
1. C 端发图 → AI 回复能引用图内容（vision 生效）。
2. 转人工后用户发图 → 客服控制台看到图。
3. 客服发图 → 用户侧聊天看到图。

- [ ] **Step 5: 最终 commit（如有验证期微调）**

```bash
git add -A
git commit -m "test: 图片附件端到端回归通过"
```

---

## Self-Review 结论

- **Spec 覆盖**：§4 存储→Task 1-2；§5 数据模型→Task 3；§6 上传→Task 4-5,8；§7 看图→Task 5,8；§8 发送绑定→Task 6,8；§9 LLM 注入→Task 7；§10 前端→Task 9-11;§11 客服控制台→Task 12;§12 成本（靠现有压缩，无新任务，已注明）；§13 测试→各 Task 内 + Task 14。全覆盖。
- **类型一致**：`bind_attachments(message_id, conv_id, uploader_id, attachment_ids)`、`_build_user_content(text, attachments)`、`Attachment={id,mime}`、`attachmentUrl(convId, id)` 各处签名一致。
- **已知待确认点（实现时以真实代码为准）**：`require_staff` 导入路径、staff 鉴权是 Bearer 还是 cookie、`test_chat_api.py` 的 client/mock fixture 复用方式、`GET /staff/.../{id}` 历史是否已含 attachments（Task 12 Step 4 注）。这些不改变设计，只影响 import/fixture 细节。
