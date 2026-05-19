# Task 5: C 端 APP JWT 验签 + JS Bridge

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

C 端 APP 通过 webview 加载本前端，APP 客户端用 JS Bridge 向前端注入 JWT；后端用 APP 后端的公钥验签。

**Files:**
- Modify: `.env.example`（加 APP_JWT_PUBLIC_KEY）
- Create: `src/ai_engine/auth/c_jwt.py`
- Create: `tests/test_auth_c_jwt.py`

- [ ] **Step 1: 加 pyjwt 依赖**

`pyproject.toml`:
```toml
dependencies = [
  # ...
  "pyjwt[crypto]>=2.9.0",
]
```

- [ ] **Step 2: `.env.example` 加配置**

```ini
# C 端 APP JWT 验签（APP 后端签发，本服务只验签不发签）
APP_JWT_PUBLIC_KEY=
APP_JWT_ALGORITHM=RS256
```

- [ ] **Step 3: `config.py` 加字段**

```python
class Settings(BaseSettings):
    # ...
    app_jwt_public_key: str = ""
    app_jwt_algorithm: str = "RS256"
```

- [ ] **Step 4: 写 `tests/test_auth_c_jwt.py`**

```python
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


@pytest.fixture
def keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    return (
        priv.private_bytes(serialization.Encoding.PEM,
                          serialization.PrivateFormat.PKCS8,
                          serialization.NoEncryption()).decode(),
        pub.public_bytes(serialization.Encoding.PEM,
                        serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
    )


async def test_verify_valid_c_jwt(monkeypatch, keypair):
    priv, pub = keypair
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("APP_JWT_PUBLIC_KEY", pub)
    from ai_engine.config import settings
    settings.reload()

    token = jwt.encode({"typ": "c", "sub": "U12345", "exp": 9999999999},
                       priv, algorithm="RS256")
    from ai_engine.auth.c_jwt import verify_app_jwt
    claims = verify_app_jwt(token)
    assert claims["typ"] == "c"
    assert claims["sub"] == "U12345"


async def test_reject_wrong_typ(monkeypatch, keypair):
    priv, pub = keypair
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("APP_JWT_PUBLIC_KEY", pub)
    from ai_engine.config import settings
    settings.reload()
    token = jwt.encode({"typ": "b", "sub": "BU1", "exp": 9999999999},
                       priv, algorithm="RS256")
    from ai_engine.auth.c_jwt import verify_app_jwt
    with pytest.raises(ValueError):
        verify_app_jwt(token)


async def test_reject_expired(monkeypatch, keypair):
    priv, pub = keypair
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("APP_JWT_PUBLIC_KEY", pub)
    from ai_engine.config import settings
    settings.reload()
    token = jwt.encode({"typ": "c", "sub": "U1", "exp": 1}, priv, algorithm="RS256")
    from ai_engine.auth.c_jwt import verify_app_jwt
    with pytest.raises(ValueError):
        verify_app_jwt(token)
```

- [ ] **Step 5: 写 `src/ai_engine/auth/c_jwt.py`**

```python
import jwt
from fastapi import HTTPException, Header
from ai_engine.config import settings


def verify_app_jwt(token: str) -> dict:
    if not settings.app_jwt_public_key:
        raise ValueError("APP_JWT_PUBLIC_KEY not configured")
    try:
        claims = jwt.decode(token, settings.app_jwt_public_key,
                            algorithms=[settings.app_jwt_algorithm])
    except jwt.PyJWTError as e:
        raise ValueError(f"invalid jwt: {e}")
    if claims.get("typ") != "c":
        raise ValueError("not a C-side jwt")
    if not claims.get("sub"):
        raise ValueError("missing sub")
    return claims


async def require_c_user(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing Bearer token")
    try:
        claims = verify_app_jwt(authorization[7:])
    except ValueError as e:
        raise HTTPException(401, str(e))
    return claims["sub"]
```

- [ ] **Step 6: 修 chat 端点支持两端**

```python
# api/chat.py
from fastapi import Depends, Request
from ai_engine.auth.bu_session import require_bu
from ai_engine.auth.c_jwt import verify_app_jwt


async def resolve_identity(request: Request) -> tuple[str, str]:
    """返回 (user_type, subject_id)。先查 Bearer（C 端）再查 cookie（B 端）。"""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            claims = verify_app_jwt(auth[7:])
            return ("c", claims["sub"])
        except ValueError:
            pass  # 落到 B 端验证
    bu_id = request.cookies.get("ai_engine_session")
    if bu_id and bu_id.startswith("BU"):
        return ("b", bu_id)
    raise HTTPException(401, "no valid identity")


@router.post("/api/v1/chat")
async def chat(body: ChatIn, request: Request):
    user_type, subject_id = await resolve_identity(request)
    conv_id = body.conversation_id
    if conv_id is None:
        conv_id = await create_conversation(user_type=user_type, subject_id=subject_id)

    async def gen():
        yield {"event": "conversation",
               "data": json.dumps({"type": "conversation",
                                   "conversation_id": conv_id,
                                   "user_type": user_type})}  # 加 user_type
        async for ev in runtime.run_turn(
            conversation_id=conv_id, user_type=user_type, subject_id=subject_id,
            user_message=body.message,
        ):
            yield {"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({"type": "done"})}

    return EventSourceResponse(gen())
```

- [ ] **Step 7: 跑测试**

```bash
pytest tests/test_auth_c_jwt.py -v
```
Expected: 3 passed

- [ ] **Step 8: Commit**

```bash
git add src/ai_engine/auth/c_jwt.py src/ai_engine/api/chat.py src/ai_engine/config.py .env.example pyproject.toml tests/test_auth_c_jwt.py
git commit -m "feat(mvp-2): C 端 APP JWT 验签 + 两端身份识别 + SSE 加 user_type 字段"
```

---
