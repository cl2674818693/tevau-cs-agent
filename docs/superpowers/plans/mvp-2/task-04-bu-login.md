# Task 4: B 端"主账户 ID 登录" + session cookie + 速率限制

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

替换 MVP-1 的 `X-BU-ID` header 临时方案。

**Files:**
- Create: `server/src/ai_engine/api/auth_bu.py`
- Modify: `server/src/ai_engine/auth/bu_session.py`（重写 session 模式）
- Create: `server/tests/test_auth_bu_login.py`

- [ ] **Step 1: 写 `server/tests/test_auth_bu_login.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport


async def test_login_valid_bu_sets_cookie(seeded_db, mysql_url):
    """有效 BU_ID → 200 + Set-Cookie"""
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU00243780"})
    assert r.status_code == 200
    assert "ai_engine_session" in r.headers.get("set-cookie", "")


async def test_login_invalid_bu_returns_generic_error(seeded_db, mysql_url):
    """无效 BU_ID → 401，错误信息不区分'不存在'和'已禁用'（防枚举）"""
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU_NOT_EXIST"})
    assert r.status_code == 401
    assert "主账户不存在或已禁用" in r.text


async def test_login_rate_limit(seeded_db, mysql_url, monkeypatch):
    """同 IP 同分钟超过 5 次 → 429"""
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        for _ in range(5):
            await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU_X"})
        r = await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU_X"})
    assert r.status_code == 429


async def test_chat_requires_session_cookie(seeded_db, mysql_url):
    """无 cookie 调 /chat → 401"""
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/api/v1/chat", json={"message": "hi"})
    assert r.status_code == 401
```

- [ ] **Step 2: 写 `server/src/ai_engine/api/auth_bu.py`**

```python
import time
from collections import defaultdict, deque
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from ai_engine.persistence.business_db import get_db


router = APIRouter()


class LoginIn(BaseModel):
    bu_id: str = Field(min_length=4, max_length=32, pattern=r"^BU[A-Za-z0-9]+$")


# 简易内存速率限制（生产换 Redis）
_RATE_BUCKET: dict[str, deque[float]] = defaultdict(deque)
RATE_LIMIT = 5     # 5 次
RATE_WINDOW = 60   # 每 60s


def _check_rate(client_ip: str) -> bool:
    now = time.time()
    q = _RATE_BUCKET[client_ip]
    while q and q[0] < now - RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return False
    q.append(now)
    return True


@router.post("/api/v1/auth/bu/login")
async def bu_login(body: LoginIn, request: Request, response: Response):
    ip = (request.client.host if request.client else "?") or "?"
    if not _check_rate(ip):
        raise HTTPException(429, "too many attempts, please wait")

    # 查 BU 存在且 active —— spec §4.1 简化方案
    db = get_db("unlimitpay")
    row = await db.fetch_one(
        "SELECT bu_id, status FROM bu WHERE bu_id=%s",
        (body.bu_id,),
    )
    if not row or int(row.get("status") or 0) != 1:
        raise HTTPException(401, "主账户不存在或已禁用")  # 通用错误，防枚举

    # 签发 session cookie（HttpOnly + Secure + SameSite=Strict + 8h）
    response.set_cookie(
        key="ai_engine_session",
        value=body.bu_id,   # MVP-2 简化：cookie 直接装 bu_id（带 HMAC 签名见 MVP-3）
        max_age=8 * 3600,
        httponly=True,
        secure=True,         # 生产 True；开发本地 http 时改 False
        samesite="strict",
    )
    return {"ok": True, "bu_id": body.bu_id}


@router.post("/api/v1/auth/bu/logout")
async def bu_logout(response: Response):
    response.delete_cookie("ai_engine_session")
    return {"ok": True}
```

- [ ] **Step 3: 重写 `server/src/ai_engine/auth/bu_session.py`**

```python
from fastapi import HTTPException, Request


async def require_bu(request: Request) -> str:
    """从 cookie 读 bu_id；MVP-2 简化方案（无 HMAC 签名），MVP-3 升级。"""
    bu_id = request.cookies.get("ai_engine_session")
    if not bu_id or not bu_id.startswith("BU"):
        raise HTTPException(401, "missing or invalid session")
    return bu_id
```

- [ ] **Step 4: `main.py` 接入 auth_bu router**

```python
# main.py 顶部 import 后追加
from ai_engine.api.auth_bu import router as auth_bu_router
app.include_router(auth_bu_router)
```

- [ ] **Step 5: 修 `server/src/ai_engine/api/chat.py` 把 require_bu 从 header → 改用新版 require_bu**

```python
# chat.py 里的 Depends(require_bu) 签名保持不变；require_bu 实现已切到 cookie
# 旧的 X-BU-ID header 实现完全删除（在 bu_session.py 里）
```

- [ ] **Step 6: 修 MVP-1 plan Task 11 的测试调用方式**

MVP-1 test 用 `headers={"X-BU-ID": "BU00243780"}`，MVP-2 改为 `cookies={"ai_engine_session": "BU00243780"}`。一并升级所有相关测试。

- [ ] **Step 7: 跑测试**

```bash
pytest tests/test_auth_bu_login.py tests/test_chat_api.py -v
```
Expected: 全部 passed

- [ ] **Step 8: Commit**

```bash
git add server/src/ai_engine/api/auth_bu.py server/src/ai_engine/auth/bu_session.py server/src/ai_engine/main.py server/src/ai_engine/api/chat.py server/tests/test_auth_bu_login.py server/tests/test_chat_api.py
git commit -m "feat(mvp-2): B 端主账户 ID 登录 + session cookie + 速率限制（替换 X-BU-ID header）"
```

---
