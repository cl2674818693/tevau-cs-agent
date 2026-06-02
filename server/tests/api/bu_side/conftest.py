"""B 端 / 座席 API 测试共用夹具。

风格对齐 server/tests/api/admin/conftest.py：
- `bu_app`：最小 FastAPI，仅挂当前文件需要的 router，绕开 main.py 的 startup 钩子
  （后者会拉 redis bridge / sweep loop / object-store bucket，单测里不需要）。
- `client_for(app)` / 各 `*_client` 夹具：基于 httpx.ASGITransport + AsyncClient。
- `auth_headers`：用 issue_staff_token 构造 Bearer 头；按角色一键切。
- `init_self_db`：初始化自有库（sqlite 临时文件），用完清掉 engine 缓存。

注：根 conftest.py 已 autouse 设 `DEV_TRUST_BU_HEADER=true` + `BU_SESSION_SECRET=test-bu-secret`。
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.auth.bu_session import issue_bu_session
from ai_engine.auth.staff_session import issue_staff_token
from ai_engine.config import settings
from ai_engine.persistence import db as db_mod
from ai_engine.persistence.db import init_db
from ai_engine.persistence.schema import now_str


@pytest.fixture
def _staff_jwt_env(monkeypatch):
    """设置 staff JWT 签名密钥（issue/verify 需要）。"""
    monkeypatch.setenv("STAFF_JWT_SECRET", "test-staff-secret")
    settings.reload()
    yield
    settings.reload()  # 让后续测试看到环境默认值


@pytest.fixture
async def init_self_db(temp_db_url: str, _staff_jwt_env) -> AsyncIterator[str]:
    """初始化自有库（sqlite 临时文件），用完清掉 engine 缓存防止跨用例串库。"""
    await init_db()
    yield temp_db_url
    eng = db_mod._engines.pop(temp_db_url, None)
    if eng is not None:
        await eng.dispose()


def _build_app(routers) -> FastAPI:
    """组一个只挂指定 router 的极简 app（不走 main 的 startup）。"""
    app = FastAPI()
    for r in routers:
        app.include_router(r)
    return app


@pytest.fixture
def make_client():
    """工厂：给定 FastAPI app 返回一个 AsyncClient 上下文管理器。"""

    def _factory(app: FastAPI) -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return _factory


# ── Staff 鉴权 helper ──────────────────────────────────────────────────────


def _staff_headers(role: str = "agent", sub: str = "agent-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_staff_token(sub, role)}"}


@pytest.fixture
def auth_headers():
    """工厂：按角色拿 staff headers。用法：auth_headers("agent") / auth_headers("admin", sub="x")。"""
    return _staff_headers


@pytest.fixture
def agent_headers(_staff_jwt_env) -> dict[str, str]:
    return _staff_headers("agent", sub="agent-1")


@pytest.fixture
def agent2_headers(_staff_jwt_env) -> dict[str, str]:
    return _staff_headers("agent", sub="agent-2")


@pytest.fixture
def senior_headers(_staff_jwt_env) -> dict[str, str]:
    return _staff_headers("senior", sub="senior-1")


@pytest.fixture
def engineer_headers(_staff_jwt_env) -> dict[str, str]:
    return _staff_headers("engineer", sub="eng-1")


@pytest.fixture
def admin_headers(_staff_jwt_env) -> dict[str, str]:
    return _staff_headers("admin", sub="admin-1")


@pytest.fixture
def supervisor_headers(_staff_jwt_env) -> dict[str, str]:
    return _staff_headers("supervisor", sub="sup-1")


# ── B 端 / C 端身份 helper ─────────────────────────────────────────────────


@pytest.fixture
def bu_headers():
    """B 端 X-BU-ID 头（DEV_TRUST_BU_HEADER=true 时直接当 tenant_id）。"""

    def _f(bu_id: str = "1011010000068") -> dict[str, str]:
        return {"X-BU-ID": bu_id}

    return _f


@pytest.fixture
def bu_cookie():
    """B 端签名 session cookie（issue_bu_session 出的 JWT）。"""

    def _f(bu_id: str = "1011010000068") -> dict[str, str]:
        from ai_engine.auth.bu_session import SESSION_COOKIE

        return {SESSION_COOKIE: issue_bu_session(bu_id)}

    return _f


# ── 数据写入 helper ────────────────────────────────────────────────────────


async def insert_conversation(
    user_type: str = "b",
    subject_id: str = "1011010000068",
    mode: str = "ai",
    archived: int = 0,
    assigned_staff_id: str | None = None,
    created_at: str | None = None,
) -> int:
    return await db_mod.insert_returning_id(
        "INSERT INTO conversations(user_type, subject_id, mode, assigned_staff_id, archived, "
        "created_at) VALUES (:ut, :sid, :mode, :asid, :ar, :now) RETURNING id",
        {
            "ut": user_type,
            "sid": subject_id,
            "mode": mode,
            "asid": assigned_staff_id,
            "ar": archived,
            "now": created_at or now_str(),
        },
    )


async def insert_message(
    conv_id: int,
    role: str = "user",
    content: str = "hi",
    status: str = "done",
    sender_staff_id: str | None = None,
    created_at: str | None = None,
) -> int:
    return await db_mod.insert_returning_id(
        "INSERT INTO messages(conversation_id, role, content, sender_staff_id, status, created_at) "
        "VALUES (:cid, :r, :c, :sid, :st, :now) RETURNING id",
        {
            "cid": conv_id,
            "r": role,
            "c": content,
            "sid": sender_staff_id,
            "st": status,
            "now": created_at or now_str(),
        },
    )


async def insert_staff(
    staff_id: str = "agent-1",
    display_name: str = "Agent One",
    role: str = "agent",
    password_plain: str = "p@ssw0rd",
    active: int = 1,
) -> int:
    from ai_engine.persistence.staff import hash_password

    return await db_mod.insert_returning_id(
        "INSERT INTO staff(staff_id, display_name, role, password_hash, active, created_at) "
        "VALUES (:sid, :name, :role, :pw, :a, :now) RETURNING id",
        {
            "sid": staff_id,
            "name": display_name,
            "role": role,
            "pw": hash_password(password_plain),
            "a": active,
            "now": now_str(),
        },
    )


async def insert_ticket(
    external_id: str = "T-001",
    conv_id: int = 1,
    severity: str = "P3",
    category: str = "card",
    created_at: str | None = None,
) -> None:
    import json

    payload = {"category": category, "severity": severity, "user_id": "U1", "user_type": "c"}
    await db_mod.execute(
        "INSERT INTO tickets(external_id, conversation_id, payload_json, current_severity, "
        "created_at) VALUES (:eid, :cid, :pj, :sev, :now)",
        {
            "eid": external_id,
            "cid": conv_id,
            "pj": json.dumps(payload, ensure_ascii=False),
            "sev": severity,
            "now": created_at or now_str(),
        },
    )


async def insert_ticket_event(
    external_id: str,
    event: str,
    actor: str | None = None,
    comment: str | None = None,
    created_at: str | None = None,
) -> None:
    import json

    await db_mod.execute(
        "INSERT INTO ticket_events(external_id, event, actor, comment, raw_json, created_at) "
        "VALUES (:eid, :e, :a, :c, :raw, :now)",
        {
            "eid": external_id,
            "e": event,
            "a": actor,
            "c": comment,
            "raw": json.dumps({}),
            "now": created_at or now_str(),
        },
    )


@pytest.fixture
def helpers() -> dict[str, Any]:
    return {
        "insert_conversation": insert_conversation,
        "insert_message": insert_message,
        "insert_staff": insert_staff,
        "insert_ticket": insert_ticket,
        "insert_ticket_event": insert_ticket_event,
    }
