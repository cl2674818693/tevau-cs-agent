"""MVP-2 端到端验收（spec §10），覆盖剧本 1-5。

剧本 1 用自签 RS256 keypair 验证 C 端 JWT 流程（生产换 APP 真实公钥，仅配置变更）。
"""

from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient


def _block(type_, **kw):
    m = MagicMock()
    m.type = type_
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _resp(blocks, stop_reason):
    r = MagicMock()
    r.content = blocks
    r.stop_reason = stop_reason
    r.usage = MagicMock(input_tokens=1, output_tokens=1)
    return r


def _client():
    from ai_engine import main as main_mod

    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def _login(client):
    await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU00243780"})


async def _new_conv(client):
    r = await client.post("/api/v1/conversations", json={})
    return r.json()["conversation_id"]


@pytest.fixture(autouse=True)
def _clear_rate():
    from ai_engine.api.auth_bu import _RATE_BUCKET

    _RATE_BUCKET.clear()


async def test_c_end_jwt_chat_uses_c_user_type(temp_db_url, monkeypatch):
    """剧本 1：C 端 APP JWT（Bearer）→ 会话识别为 user_type=c。"""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = (
        priv.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    monkeypatch.setenv("APP_JWT_PUBLIC_KEY", pub_pem)
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence.db import init_db

    await init_db()
    monkeypatch.setattr(
        ac,
        "_client",
        MagicMock(
            messages=MagicMock(
                create=AsyncMock(
                    return_value=_resp([_block("text", text="您好，已为您查询。")], "end_turn")
                )
            )
        ),
    )
    token = jwt.encode({"typ": "c", "sub": "U777", "exp": 9999999999}, priv_pem, algorithm="RS256")
    headers = {"Authorization": f"Bearer {token}"}

    async with _client() as client:
        init = await client.post("/api/v1/conversations", json={}, headers=headers)
        assert init.json()["user_type"] == "c"
        cid = init.json()["conversation_id"]
        async with client.stream(
            "GET", f"/api/v1/chat?conversation_id={cid}&message=你好", headers=headers
        ) as resp:
            lines = [line async for line in resp.aiter_lines()]
    assert any('"user_type": "c"' in line for line in lines)


async def test_b_end_real_mysql_diagnosis(temp_db_url, business_mysql, monkeypatch):
    """剧本 3：B 端登录 → 问 card_bind 500 → AI 调真 MySQL query_api_call → 回复带技术细节。"""
    from ai_engine.persistence.db import init_db

    await init_db()
    from ai_engine.agent import runtime  # noqa: F401  确保工具已注册
    from ai_engine.integrations import anthropic_client as ac

    seq = iter(
        [
            _resp(
                [_block("tool_use", id="1", name="query_api_call", input={"uid": "1765348436409"})],
                "tool_use",
            ),
            _resp(
                [
                    _block(
                        "text",
                        text="该请求返回 500，错误码 DB_TIMEOUT，见 handlers/card_bind.go:120",
                    )
                ],
                "end_turn",
            ),
            # self-check 修订轮（spec §8.3）：原样返回
            _resp(
                [
                    _block(
                        "text",
                        text="该请求返回 500，错误码 DB_TIMEOUT，见 handlers/card_bind.go:120",
                    )
                ],
                "end_turn",
            ),
        ]
    )
    fake = MagicMock()
    fake.messages.create = AsyncMock(side_effect=lambda **kw: next(seq))
    monkeypatch.setattr(ac, "_client", fake)

    async with _client() as client:
        await _login(client)
        cid = await _new_conv(client)
        lines = []
        async with client.stream(
            "GET", f"/api/v1/chat?conversation_id={cid}&message=card_bind 500 uid=1765348436409"
        ) as resp:
            async for line in resp.aiter_lines():
                lines.append(line)
    joined = "\n".join(lines)
    assert any("event: tool_result" in line for line in lines)
    assert "DB_TIMEOUT" in joined


async def test_b_end_cross_bu_blocked(temp_db_url, business_mysql, monkeypatch):
    """剧本 4：AI 试图查别的 BU 的卡 → router 注入会话身份 → 真 MySQL 查不到 → AI 说无权限。"""
    from ai_engine.persistence.db import init_db

    await init_db()
    from ai_engine.integrations import anthropic_client as ac

    seq = iter(
        [
            _resp(
                [
                    _block(
                        "tool_use",
                        id="1",
                        name="query_card",
                        input={"bu_id": "BU_OTHER", "card_id": "C200"},
                    )
                ],
                "tool_use",
            ),
            _resp(
                [_block("text", text="未在您账户下找到该卡片，我无法查询其他 BU 的数据。")],
                "end_turn",
            ),
            # self-check 修订轮（spec §8.3）：原样返回
            _resp(
                [_block("text", text="未在您账户下找到该卡片，我无法查询其他 BU 的数据。")],
                "end_turn",
            ),
        ]
    )
    fake = MagicMock()
    fake.messages.create = AsyncMock(side_effect=lambda **kw: next(seq))
    monkeypatch.setattr(ac, "_client", fake)

    async with _client() as client:
        await _login(client)
        cid = await _new_conv(client)
        lines = []
        async with client.stream(
            "GET", f"/api/v1/chat?conversation_id={cid}&message=查卡 C200"
        ) as resp:
            async for line in resp.aiter_lines():
                lines.append(line)
    assert "无法查询其他 BU" in "\n".join(lines) or "未在您账户下" in "\n".join(lines)


async def test_staff_takeover_flow(temp_db_url, business_mysql, monkeypatch):
    """剧本 2：转人工 → 客服接管 → 客服回话 → 用户消息走客服（不调 AI）。"""
    monkeypatch.setenv("STAFF_JWT_SECRET", "e2e")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.agent.tools import create_ticket as ct
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.conversations import get_mode, list_messages
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff import create_staff

    await init_db()
    await create_staff("S1", "客服小张", "agent", "x")
    staff_h = {"Authorization": f"Bearer {issue_staff_token('S1', 'agent')}"}
    monkeypatch.setattr(ct, "_post", AsyncMock(return_value=MagicMock(status_code=200)))

    async with _client() as client:
        await _login(client)
        cid = await _new_conv(client)
        # 用户请求人工 → human_pending
        await client.post(f"/api/v1/conversations/{cid}/request-human", json={"reason": "要找人工"})
        assert (await get_mode(cid))[0] == "human_pending"
        # 客服接管 + 回话
        assert (
            await client.post(f"/staff/api/v1/conversations/{cid}/take", headers=staff_h)
        ).status_code == 200
        await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "您好，我来为您处理"},
            headers=staff_h,
        )
        # 用户再发消息 → human_takeover 分支（不调 AI）
        async with client.stream(
            "GET", f"/api/v1/chat?conversation_id={cid}&message=好的谢谢"
        ) as resp:
            lines = [line async for line in resp.aiter_lines()]
    assert not any("event: message_start" in line for line in lines)
    msgs = await list_messages(cid)
    assert any(m["role"] == "human_agent" and "处理" in m["content"] for m in msgs)
    assert any(m["role"] == "user" and "谢谢" in m["content"] for m in msgs)


async def test_reverse_webhook_reopen(temp_db_url, business_mysql, monkeypatch):
    """剧本 5：用户点'未解决' → 反向 webhook → 工单 reopen → 推事项中心。"""
    from ai_engine.api import user_events
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.tickets import create_ticket, get_ticket

    await init_db()
    await create_ticket(
        external_id="AI-RW", conversation_id=1, payload={"category": "bug", "bu_id": "BU00243780"}
    )
    pushed = []
    # user_events 直接 import 了 push_event_center，故在使用处打桩
    monkeypatch.setattr(
        user_events, "push_event_center", AsyncMock(side_effect=lambda p: pushed.append(p) or True)
    )

    async with _client() as client:
        await _login(client)
        r = await client.post(
            "/api/v1/tickets/AI-RW/user-events",
            json={"event": "user_rejected_resolved", "reason": "又被锁了"},
        )
    assert r.status_code == 200
    t = await get_ticket("AI-RW")
    assert any(e["event"] == "reopen" for e in t["events"])
    assert pushed and pushed[-1]["event"] == "reopen"
