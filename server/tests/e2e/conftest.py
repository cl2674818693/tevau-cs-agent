"""e2e 测试共用夹具。

e2e 测试 = 跨多个 API / 模块的完整业务剧本，目标验证全链路而非单个端点。

约束（不变量）：
- 用 sqlite 自有库（顶层 `temp_db_url` 提供临时文件 URL）；用例间隔离。
- 用 `httpx.AsyncClient + ASGITransport(app)` 走 in-process ASGI；不开 lifespan，自己 init_db。
- LLM / 业务外部依赖统统 mock：
  - `runtime.run_turn` —— 用户 chat 流（默认走 stub）；
  - `runtime.collect_full_response` —— ai_draft 模式；
  - `httpx.AsyncClient.post` 在事项中心调用处 —— 用 monkeypatch 短路；
  - `c_session.resolve_c_user` —— Bearer → user_code 映射；
- 进程内 rate_limit 窗口、subscriber 总线、_cancel_signals、 prompt cache 在每个 case 后清理。

注意：所有 dict/list payload 在测试里用 ``ensure_ascii=False`` 序列化的 SSE 与中文友好。
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_engine.auth import c_session as _c_session
from ai_engine.auth.bu_session import SESSION_COOKIE, issue_bu_session
from ai_engine.auth.staff_session import issue_staff_token
from ai_engine.config import settings
from ai_engine.governance import rate_limit as _rl
from ai_engine.main import app
from ai_engine.persistence import db as db_mod
from ai_engine.persistence.db import init_db

# ───── 常量 ──────────────────────────────────────────────────────────
USER_CODE_A = "U-ALPHA"
USER_CODE_B = "U-BETA"
TOKEN_A = "sa-token-alpha"
TOKEN_B = "sa-token-beta"
BU_ID = "1011010000068"


def c_headers(token: str = TOKEN_A) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def bu_headers(bu_id: str = BU_ID) -> dict[str, str]:
    return {"X-BU-ID": bu_id}


def staff_headers(staff_id: str = "agent-1", role: str = "agent") -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_staff_token(staff_id, role)}"}


# ───── 环境与外部依赖统一 mock ─────────────────────────────────────────


@pytest.fixture
def _staff_jwt_env(monkeypatch):
    """staff JWT 密钥；32 字节起步避免 PyJWT 短密钥告警污染输出。"""
    monkeypatch.setenv("STAFF_JWT_SECRET", "test-staff-secret-" + "x" * 32)
    settings.reload()
    yield
    settings.reload()


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    """每 case 清进程内窗口，避免 30/min 跨用例累计后被误触发。"""
    _rl.reset()
    yield
    _rl.reset()


@pytest.fixture(autouse=True)
def _reset_subscriber_bus() -> None:
    """清空 staff_conversations 进程内事件订阅总线，避免 case 间窜事件。"""
    from ai_engine.api import staff_conversations as sc

    sc._subscribers.clear()
    yield
    sc._subscribers.clear()


@pytest.fixture(autouse=True)
def _reset_cancel_signals() -> None:
    """清空 chat 模块进程内取消信号字典。"""
    from ai_engine.api import chat as _chat

    _chat._cancel_signals.clear()
    yield
    _chat._cancel_signals.clear()


@pytest.fixture(autouse=True)
def _mock_c_identity(monkeypatch) -> dict[str, str]:
    """token → user_code 短路，避开真实 c gateway。"""
    table = {TOKEN_A: USER_CODE_A, TOKEN_B: USER_CODE_B}

    async def _fake(token: str) -> str | None:
        return table.get(token)

    monkeypatch.setattr(_c_session, "resolve_c_user", _fake)
    from ai_engine.auth import bu_session as _bs

    monkeypatch.setattr(_bs, "resolve_c_user", _fake)
    return table


@pytest.fixture(autouse=True)
def _mock_event_center(monkeypatch) -> list[dict[str, Any]]:
    """拦截 create_ticket 工具 + push_event_center 出口的 HTTP POST。

    返回 inbox：测试可断言事项中心收到了哪些 payload。
    """
    inbox: list[dict[str, Any]] = []

    class _FakeResp:
        status_code = 200

    async def _fake_post(url: str, json: dict[str, Any], headers: dict[str, str]):
        inbox.append({"url": url, "json": json, "headers": headers})
        return _FakeResp()

    from ai_engine.agent.tools import create_ticket as _ct

    monkeypatch.setattr(_ct, "_post", _fake_post)

    from ai_engine.integrations import event_center_client as _ec

    async def _fake_push(payload: dict[str, Any]) -> bool:
        inbox.append({"push": payload})
        return True

    monkeypatch.setattr(_ec, "push_event_center", _fake_push)
    # tickets 模块通过 _publish 调度，但 maintenance / user_events 直接 import
    from ai_engine.api import user_events as _ue
    from ai_engine.persistence import maintenance as _m

    monkeypatch.setattr(_ue, "push_event_center", _fake_push)
    monkeypatch.setattr(_m, "push_event_center", _fake_push)
    return inbox


@pytest.fixture(autouse=True)
def _mock_lark(monkeypatch) -> list[dict[str, Any]]:
    """拦截 Lark webhook 出口（防 create_ticket 兜底真打 https）。"""
    sent: list[dict[str, Any]] = []

    async def _fake_send(payload: dict[str, Any]) -> None:
        sent.append(payload)

    from ai_engine.agent.tools import create_ticket as _ct

    monkeypatch.setattr(_ct, "_notify_lark", _fake_send)
    from ai_engine.api import feedback as _fb

    monkeypatch.setattr(_fb, "_notify_lark", _fake_send)
    return sent


# ───── DB / Client / Session helpers ───────────────────────────────────


@pytest_asyncio.fixture
async def db_ready(temp_db_url: str, _staff_jwt_env) -> AsyncIterator[str]:
    """初始化自有库 schema；用完清 engine 缓存 + prompt cache。"""
    await init_db()
    yield temp_db_url
    # prompt loader 缓存清掉，避免不同 case 的 prompts_dir 改动残留
    from ai_engine.prompts import loader

    loader.clear_cache()
    for eng in list(db_mod._engines.values()):
        await eng.dispose()
    db_mod._engines.clear()


@pytest_asyncio.fixture
async def client(db_ready: str) -> AsyncIterator[AsyncClient]:
    """裸 HTTP 客户端（不带身份）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def c_client(db_ready: str) -> AsyncIterator[AsyncClient]:
    """C 端 A 身份客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=c_headers(TOKEN_A)
    ) as c:
        yield c


@pytest_asyncio.fixture
async def bu_client(db_ready: str) -> AsyncIterator[AsyncClient]:
    """B 端身份客户端（DEV_TRUST_BU_HEADER=true → X-BU-ID 即 tenant）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=bu_headers(BU_ID)
    ) as c:
        yield c


@pytest_asyncio.fixture
async def make_staff_client(db_ready: str):
    """工厂：返回带某 staff_id/role 身份的 AsyncClient（调用方负责 close）。"""
    clients: list[AsyncClient] = []

    def _factory(staff_id: str = "agent-1", role: str = "agent") -> AsyncClient:
        c = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers=staff_headers(staff_id, role),
        )
        clients.append(c)
        return c

    yield _factory
    for c in clients:
        await c.aclose()


# ───── 业务态预置 ───────────────────────────────────────────────────────


async def insert_staff_row(
    staff_id: str = "agent-1",
    display_name: str = "Agent One",
    role: str = "agent",
    active: int = 1,
) -> None:
    """直接落 staff 行（不走加密的真实 password 校验路径）。"""
    from ai_engine.persistence.schema import now_str
    from ai_engine.persistence.staff import hash_password

    await db_mod.execute(
        "INSERT INTO staff(staff_id, display_name, role, password_hash, active, created_at) "
        "VALUES (:sid, :name, :role, :pw, :a, :now)",
        {
            "sid": staff_id,
            "name": display_name,
            "role": role,
            "pw": hash_password("not-used-in-e2e"),
            "a": active,
            "now": now_str(),
        },
    )


@pytest_asyncio.fixture
async def seeded_agent(db_ready):
    """预置一个 agent-1 行（部分剧本 _human_message_event 查 display_name 用）。"""
    await insert_staff_row("agent-1", "Agent One", "agent")
    return "agent-1"


# ───── 工具：runtime mock ──────────────────────────────────────────────


def stub_run_turn(monkeypatch, events_or_factory) -> None:
    """把 runtime.run_turn 换成给定事件序列 / 工厂；同时模拟真实 runtime 的关键持久化副作用。

    events_or_factory:
      - list[dict]：每次调用都 yield 同一序列
      - list[list[dict]]：按调用次数轮换序列（第一次用 [0]，第二次用 [1]…）
      - callable(**kwargs) -> list[dict]：动态决定

    副作用：每次调用都会
        - append_user_turn(conversation_id, user_message, client_message_id) → turn_id
        - 把流出的 text 拼接落库（assistant 行 json blocks 格式）
        - finalize_turn(turn_id, "done")
    这样 chat 端点的"按 cmid 幂等重放"、"history 端点能看到 assistant 文本"等真实链路才能跑通。
    """
    state = {"call_idx": 0}

    def _resolve(kw: dict[str, Any]) -> list[dict[str, Any]]:
        v = events_or_factory
        if callable(v):
            return v(**kw)
        if v and isinstance(v[0], list):
            seq = v[state["call_idx"] % len(v)]
            state["call_idx"] += 1
            return seq
        return list(v)

    async def _persist_turn(
        conversation_id: int,
        user_message: str,
        client_message_id: str | None,
        events: list[dict[str, Any]],
        subject_id: str | None = None,
        attachment_ids: list[int] | None = None,
    ) -> None:
        # 模拟 runtime 的最小持久化：user_turn → done + assistant blocks 落库；
        # 若带 attachment_ids 也复刻 runtime 的 bind_attachments(归属/未绑定才生效)。
        from ai_engine.persistence.conversations import (
            append_message,
            append_user_turn,
            finalize_turn,
        )

        turn_id = await append_user_turn(conversation_id, user_message, client_message_id)
        if attachment_ids:
            from ai_engine.persistence import attachments as att_dao

            await att_dao.bind_attachments(
                turn_id, conversation_id, subject_id or "", attachment_ids
            )
        texts = [e["text"] for e in events if e.get("type") == "text"]
        if texts:
            await append_message(
                conversation_id,
                role="assistant",
                content=json.dumps(
                    [{"type": "text", "text": t} for t in texts], ensure_ascii=False
                ),
            )
        await finalize_turn(turn_id, "done")

    async def _fake_run_turn(**kwargs: Any):
        events = _resolve(kwargs)
        await _persist_turn(
            kwargs.get("conversation_id"),
            kwargs.get("user_message", ""),
            kwargs.get("client_message_id"),
            events,
            subject_id=kwargs.get("subject_id"),
            attachment_ids=kwargs.get("attachment_ids") or [],
        )
        for ev in events:
            yield ev

    async def _fake_collect(**kwargs: Any) -> str:
        events = _resolve(kwargs)
        # collect_full_response 是 ai_draft 路径用的；按真实行为不落 assistant 行，
        # 但仍需要 user_turn 入库 + done（否则 admin 列表/限流统计偏差）
        await _persist_turn(
            kwargs.get("conversation_id"),
            kwargs.get("user_message", ""),
            kwargs.get("client_message_id"),
            events=[],  # 不落 assistant 行；草稿走 save_ai_draft
            subject_id=kwargs.get("subject_id"),
            attachment_ids=kwargs.get("attachment_ids") or [],
        )
        return "".join(ev.get("text", "") for ev in events if ev.get("type") == "text")

    from ai_engine.agent import runtime as _rt
    from ai_engine.api import chat as _chat

    monkeypatch.setattr(_chat.runtime, "run_turn", _fake_run_turn)
    monkeypatch.setattr(_rt, "collect_full_response", _fake_collect)


async def parse_sse(response) -> list[dict[str, str]]:
    """把 httpx SSE Response 文本拆成 [{event, data, id?}, …]。

    sse-starlette 实际行分隔用 \\r\\n（CRLF），先规整为 \\n 再切。
    """
    text = response.text.replace("\r\n", "\n").replace("\r", "\n")
    frames: list[dict[str, str]] = []
    for blk in text.split("\n\n"):
        blk = blk.strip()
        if not blk or blk.startswith(":"):
            continue
        cur: dict[str, str] = {}
        for line in blk.splitlines():
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                cur["event"] = line[len("event:") :].strip()
            elif line.startswith("data:"):
                cur["data"] = cur.get("data", "") + line[len("data:") :].strip()
            elif line.startswith("id:"):
                cur["id"] = line[len("id:") :].strip()
        if cur:
            frames.append(cur)
    return frames


def event_data(frames: list[dict[str, str]], event_name: str) -> list[dict[str, Any]]:
    """从 SSE frames 取所有指定 event 的 data dict。"""
    out: list[dict[str, Any]] = []
    for f in frames:
        if f.get("event") == event_name and f.get("data"):
            try:
                out.append(json.loads(f["data"]))
            except json.JSONDecodeError:
                pass
    return out


# 暴露给测试使用
__all__ = [
    "BU_ID",
    "SESSION_COOKIE",
    "TOKEN_A",
    "TOKEN_B",
    "USER_CODE_A",
    "USER_CODE_B",
    "asyncio",
    "bu_headers",
    "c_headers",
    "event_data",
    "insert_staff_row",
    "issue_bu_session",
    "parse_sse",
    "staff_headers",
    "stub_run_turn",
]
