"""admin API 测试共用夹具。

- `admin_app`：最小 FastAPI 仅挂载被测 admin router 子集，绕开 main.py 的 startup 钩子
  （后者会拉 redis bridge / sweep loop / object-store bucket，单测里不需要）。
- `client` / `client_factory`：基于 httpx.ASGITransport + AsyncClient（asyncio 模式与项目对齐）。
- `auth_headers`：用 issue_staff_token 构造 Bearer 头，按角色一键切。
- `init_self_db`：初始化自有库表，并在测试结束后清空 db engine 缓存防止跨用例串库。
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.auth.staff_session import issue_staff_token
from ai_engine.config import settings
from ai_engine.persistence import db as db_mod
from ai_engine.persistence.db import init_db


@pytest.fixture
def _staff_jwt_env(monkeypatch):
    """设置 staff JWT 签名密钥（issue/verify 需要）。"""
    # 32 字节起步，避免 PyJWT InsecureKeyLengthWarning 干扰输出
    monkeypatch.setenv("STAFF_JWT_SECRET", "test-staff-secret-" + "x" * 32)
    settings.reload()
    yield
    settings.reload()  # 让后续测试看到环境默认值


@pytest.fixture
async def init_self_db(temp_db_url: str, _staff_jwt_env) -> AsyncIterator[str]:
    """初始化自有库（sqlite 临时文件），用完清掉 engine 缓存与 RBAC 缓存。"""
    await init_db()
    # rbac 模块内带进程级缓存，跨用例残留会污染矩阵断言
    from ai_engine.persistence import rbac

    rbac.invalidate_cache()
    yield temp_db_url
    rbac.invalidate_cache()
    # 关掉本 url 对应的 engine，避免下个用例还指向已删的临时文件
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
def admin_app():
    """默认挂全部 admin + insights + metrics 路由；测试用例直接复用即可。"""
    from ai_engine.api.admin_dashboard import router as admin_dashboard_router
    from ai_engine.api.admin_rbac import router as admin_rbac_router
    from ai_engine.api.admin_shifts import router as admin_shifts_router
    from ai_engine.api.admin_sla import router as admin_sla_router
    from ai_engine.api.admin_staff import router as admin_staff_router
    from ai_engine.api.insights import router as insights_router
    from ai_engine.api.metrics import router as metrics_router

    return _build_app(
        [
            admin_dashboard_router,
            admin_rbac_router,
            admin_shifts_router,
            admin_sla_router,
            admin_staff_router,
            insights_router,
            metrics_router,
        ]
    )


@pytest.fixture
async def client(admin_app) -> AsyncIterator[AsyncClient]:
    """异步 HTTP 客户端：走 ASGI in-process，没有真实端口。"""
    transport = ASGITransport(app=admin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _headers(role: str, sub: str = "tester") -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_staff_token(sub, role)}"}


@pytest.fixture
def auth_headers():
    """工厂：按角色拿 headers。用法：auth_headers("admin") / auth_headers("agent")。"""
    return _headers


@pytest.fixture
def admin_headers(_staff_jwt_env) -> dict[str, str]:
    return _headers("admin", sub="admin-1")


@pytest.fixture
def agent_headers(_staff_jwt_env) -> dict[str, str]:
    return _headers("agent", sub="agent-1")


@pytest.fixture
def supervisor_headers(_staff_jwt_env) -> dict[str, str]:
    return _headers("supervisor", sub="sup-1")


@pytest.fixture
def manager_headers(_staff_jwt_env) -> dict[str, str]:
    return _headers("manager", sub="mgr-1")


# 便捷数据写入（多个测试文件复用）
async def insert_conversation(
    user_type: str = "c",
    subject_id: str = "U1",
    mode: str = "ai",
    archived: int = 0,
    created_at: str | None = None,
) -> int:
    from ai_engine.persistence.schema import now_str

    return await db_mod.insert_returning_id(
        "INSERT INTO conversations(user_type, subject_id, mode, archived, created_at) "
        "VALUES (:ut, :sid, :mode, :ar, :now) RETURNING id",
        {
            "ut": user_type,
            "sid": subject_id,
            "mode": mode,
            "ar": archived,
            "now": created_at or now_str(),
        },
    )


async def insert_staff_action(
    conv_id: int, staff_id: str, action: str, at: str | None = None,
) -> None:
    from ai_engine.persistence.schema import now_str

    await db_mod.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (:cid, :sid, :a, :at)",
        {"cid": conv_id, "sid": staff_id, "a": action, "at": at or now_str()},
    )


async def insert_message(
    conv_id: int,
    role: str,
    content: str = "x",
    status: str = "done",
    topic_verdict: str | None = None,
    prompt_version: str | None = None,
    created_at: str | None = None,
) -> int:
    from ai_engine.persistence.schema import now_str

    return await db_mod.insert_returning_id(
        "INSERT INTO messages(conversation_id, role, content, status, topic_verdict, "
        "prompt_version, created_at) "
        "VALUES (:cid, :r, :c, :st, :tv, :pv, :now) RETURNING id",
        {
            "cid": conv_id,
            "r": role,
            "c": content,
            "st": status,
            "tv": topic_verdict,
            "pv": prompt_version,
            "now": created_at or now_str(),
        },
    )


async def insert_feedback(
    conv_id: int,
    message_id: int,
    rating: str = "down",
    subject_id: str = "U1",
    user_type: str = "c",
    created_at: str | None = None,
) -> None:
    from ai_engine.persistence.schema import now_str

    await db_mod.execute(
        "INSERT INTO message_feedback(conversation_id, message_id, rating, subject_id, "
        "user_type, created_at) VALUES (:cid, :mid, :r, :sid, :ut, :now)",
        {
            "cid": conv_id,
            "mid": message_id,
            "r": rating,
            "sid": subject_id,
            "ut": user_type,
            "now": created_at or now_str(),
        },
    )


async def insert_tool_audit(
    conv_id: int,
    tool_name: str,
    is_empty: int | None = 0,
    rejected: int = 0,
    created_at: str | None = None,
) -> None:
    import json

    from ai_engine.persistence.schema import now_str

    await db_mod.execute(
        "INSERT INTO tool_audits(conversation_id, tool_name, params_json, result_size, "
        "duration_ms, rejected, is_empty, created_at) "
        "VALUES (:cid, :tn, :pj, 0, 0, :rj, :ie, :now)",
        {
            "cid": conv_id,
            "tn": tool_name,
            "pj": json.dumps({}),
            "rj": int(rejected),
            "ie": is_empty,
            "now": created_at or now_str(),
        },
    )


# 暴露 helper 给测试文件（避免每个文件都重写一份）
@pytest.fixture
def helpers() -> dict[str, Any]:
    return {
        "insert_conversation": insert_conversation,
        "insert_staff_action": insert_staff_action,
        "insert_message": insert_message,
        "insert_feedback": insert_feedback,
        "insert_tool_audit": insert_tool_audit,
    }
