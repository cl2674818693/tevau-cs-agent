"""C 端 API 测试通用夹具。

集中处理：
- 临时 sqlite 自有库（temp_db_url 已由顶层 conftest 暴露；此处显式 init_db + 关引擎）
- C 端身份 mock：patch `auth.c_session.resolve_c_user` 直接返回 user_code，避开 c gateway
- 进程内 rate_limit 重置（顶层 reset 不 autouse，故在这里 wipe）
- httpx AsyncClient（绑定 ASGITransport，跑同一个 FastAPI app）
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_engine.auth import c_session as _c_session
from ai_engine.governance import rate_limit as _rl
from ai_engine.main import app
from ai_engine.persistence.db import _engines, init_db


# ───────────────── 通用常量 ─────────────────

USER_CODE_A = "U-ALPHA"          # 主测试 C 端用户
USER_CODE_B = "U-BETA"           # 越权 / 第二用户
TOKEN_A = "sa-token-alpha-xxx"   # 任意串；由我们 mock 的 resolve_c_user 解析
TOKEN_B = "sa-token-beta-xxx"


def auth_headers(token: str = TOKEN_A) -> dict[str, str]:
    """C 端身份：Authorization: Bearer <Sa-Token>。"""
    return {"Authorization": f"Bearer {token}"}


# ───────────────── 基础环境夹具 ─────────────────


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    """每个 case 跑前清掉进程内窗口，避免 30/min 上限被跨用例累计触发。"""
    _rl.reset()
    yield
    _rl.reset()


@pytest_asyncio.fixture
async def db_ready(temp_db_url: str) -> AsyncIterator[str]:
    """初始化自有库 schema（基于顶层 temp_db_url 的临时 sqlite）。

    每个用例独立文件 → 表也独立；用例结束后顶层 fixture 会清掉文件。
    顺带在每个 case 后 dispose 引擎，防止文件被复用时旧连接命中已删除文件。
    """
    await init_db()
    yield temp_db_url
    for eng in list(_engines.values()):
        await eng.dispose()
    _engines.clear()


@pytest.fixture(autouse=True)
def _mock_c_identity(monkeypatch) -> dict[str, str]:
    """把 c_session.resolve_c_user 短路为 token→user_code 映射，避免打 c gateway。

    返回当前映射，便于个别用例新增/清空。
    """
    table = {TOKEN_A: USER_CODE_A, TOKEN_B: USER_CODE_B}

    async def _fake(token: str) -> str | None:
        return table.get(token)

    # bu_session.resolve_identity 内部 import 了 resolve_c_user，要 patch 顶层定义点
    monkeypatch.setattr(_c_session, "resolve_c_user", _fake)
    from ai_engine.auth import bu_session as _bs

    monkeypatch.setattr(_bs, "resolve_c_user", _fake)
    return table


@pytest_asyncio.fixture
async def client(db_ready: str) -> AsyncIterator[AsyncClient]:
    """裸 httpx.AsyncClient（不带身份头）—— 401/未登录路径用它。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def c_client(db_ready: str) -> AsyncIterator[AsyncClient]:
    """C 端身份 A 的 client（默认带 Authorization）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=auth_headers(TOKEN_A)
    ) as c:
        yield c


# ───────────────── 业务态预置 ─────────────────


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    """为 USER_CODE_A 起一条新会话；返回 conversation_id。"""
    r = await c_client.post("/api/v1/conversations", json={})
    assert r.status_code == 200, r.text
    return int(r.json()["conversation_id"])


@pytest_asyncio.fixture
async def other_conv_id(db_ready: str) -> int:
    """USER_CODE_B 的会话；用于越权验证（A 不能查 B 的会话）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=auth_headers(TOKEN_B)
    ) as c:
        r = await c.post("/api/v1/conversations", json={})
        assert r.status_code == 200
        return int(r.json()["conversation_id"])


# ───────────────── runtime mock helpers ─────────────────


def stub_run_turn(monkeypatch, events: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """把 runtime.run_turn 换成一个固定事件序列生成器。

    返回 events 列表的引用——调用方可后续 append 来追加事件（不常用）。
    默认事件：先 text 再无 → chat 端点会自动加 message_start/stop 帧。
    """
    seq = events or [{"type": "text", "text": "你好，我是 AI"}]

    async def _fake_run_turn(**_kwargs: Any):
        for ev in seq:
            yield ev

    from ai_engine.agent import runtime
    from ai_engine.api import chat as _chat

    # chat.py 用 `runtime.run_turn` 模块属性引用，patch 模块属性即可
    monkeypatch.setattr(_chat.runtime, "run_turn", _fake_run_turn)
    # collect_full_response 内部又调 run_turn，单独 patch 一份保险（ai_draft 路径走它）

    async def _fake_collect(**_kwargs: Any) -> str:
        # 把所有 text 事件拼起来（与原实现一致）
        return "".join(ev.get("text", "") for ev in seq if ev.get("type") == "text")

    monkeypatch.setattr(runtime, "collect_full_response", _fake_collect)
    return seq


async def parse_sse(response) -> list[dict[str, str]]:
    """把一个 httpx Response（SSE）拆成 [{event, data}, ...]。

    sse-starlette 的输出行分隔符是 CRLF（\\r\\n），帧间隔是 \\r\\n\\r\\n；
    我们统一把 \\r\\n 替换成 \\n 再按 \\n\\n 拆。
    某些帧（comment / ping）以 ":" 开头，本函数跳过。
    """
    text = response.text.replace("\r\n", "\n")
    frames: list[dict[str, str]] = []
    for blk in text.split("\n\n"):
        blk = blk.strip()
        if not blk or blk.startswith(":"):
            continue
        cur: dict[str, str] = {}
        for line in blk.splitlines():
            if line.startswith(":"):  # comment / ping
                continue
            if line.startswith("event:"):
                cur["event"] = line[len("event:"):].strip()
            elif line.startswith("data:"):
                cur["data"] = (cur.get("data", "") + line[len("data:"):].strip())
            elif line.startswith("id:"):
                cur["id"] = line[len("id:"):].strip()
        if cur:
            frames.append(cur)
    return frames
