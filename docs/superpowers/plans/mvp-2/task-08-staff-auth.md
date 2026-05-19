# Task 8: 客服 JWT + 客服登录端点

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `server/src/ai_engine/auth/staff_session.py`
- Create: `server/src/ai_engine/api/staff_auth.py`
- Create: `server/tests/test_staff_auth.py`

- [ ] **Step 1: `server/.env.example` 加配置**

```ini
# 客服 JWT 签名密钥（HS256，本服务签发本服务验证）
STAFF_JWT_SECRET=
```

- [ ] **Step 2: `config.py` 加字段**

```python
staff_jwt_secret: str = ""
```

- [ ] **Step 3: 写 `server/src/ai_engine/auth/staff_session.py`**

```python
import jwt
import time
from fastapi import HTTPException, Header
from ai_engine.config import settings


def issue_staff_token(staff_id: str, role: str) -> str:
    return jwt.encode(
        {"typ": "staff", "sub": staff_id, "role": role, "exp": int(time.time()) + 8 * 3600},
        settings.staff_jwt_secret, algorithm="HS256",
    )


def verify_staff_token(token: str) -> dict:
    try:
        claims = jwt.decode(token, settings.staff_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise ValueError(str(e))
    if claims.get("typ") != "staff":
        raise ValueError("not staff token")
    return claims


async def require_staff(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing staff token")
    try:
        return verify_staff_token(authorization[7:])
    except ValueError as e:
        raise HTTPException(401, str(e))
```

- [ ] **Step 4: 写 `server/src/ai_engine/api/staff_auth.py`**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ai_engine.persistence.staff import authenticate
from ai_engine.auth.staff_session import issue_staff_token


router = APIRouter()


class StaffLoginIn(BaseModel):
    staff_id: str
    password: str


@router.post("/staff/api/v1/auth/login")
async def staff_login(body: StaffLoginIn):
    s = await authenticate(body.staff_id, body.password)
    if not s:
        raise HTTPException(401, "invalid credentials")
    token = issue_staff_token(s["staff_id"], s["role"])
    return {"token": token, "staff": s}
```

- [ ] **Step 5: 写 `server/tests/test_staff_auth.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport


async def test_staff_login_success(temp_db_url, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test-secret")
    from ai_engine.config import settings
    settings.reload()

    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff import create_staff
    await init_db()
    await create_staff("S100", "张三", "agent", "secret123")

    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/staff/api/v1/auth/login",
                              json={"staff_id": "S100", "password": "secret123"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data["staff"]["display_name"] == "张三"


async def test_staff_login_wrong_password(temp_db_url, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test-secret")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff import create_staff
    await init_db()
    await create_staff("S100", "张三", "agent", "secret123")

    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/staff/api/v1/auth/login",
                              json={"staff_id": "S100", "password": "WRONG"})
    assert r.status_code == 401
```

- [ ] **Step 6: 跑测试 + Commit**

```bash
pytest tests/test_staff_auth.py -v
git add server/src/ai_engine/auth/staff_session.py server/src/ai_engine/api/staff_auth.py server/tests/test_staff_auth.py server/src/ai_engine/config.py .env.example
git commit -m "feat(mvp-2): 客服 JWT + 登录端点"
```

---
