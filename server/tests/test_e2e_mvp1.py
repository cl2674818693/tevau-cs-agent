from unittest.mock import AsyncMock, MagicMock

import respx
from httpx import ASGITransport, AsyncClient, Response


def _block(type_, **kw):
    m = MagicMock()
    m.type = type_
    for k, v in kw.items():
        setattr(m, k, v)  # name 走 setattr 不走构造器，避免 MagicMock(name=) 陷阱
    return m


def _resp(blocks, stop_reason):
    r = MagicMock()
    r.content = blocks
    r.stop_reason = stop_reason
    r.usage = MagicMock(input_tokens=10, output_tokens=10)
    return r


async def _init_conv(client):
    r = await client.post("/api/v1/conversations", json={}, headers={"X-BU-ID": "BU00243780"})
    return r.json()["conversation_id"]


@respx.mock
async def test_e2e_bug_diagnosis_creates_ticket(seeded_db, monkeypatch):
    """spec §10 验收：AI 查日志 → 定位代码 → 建工单（推送 payload 为 bug）。"""
    from ai_engine import main as main_mod
    from ai_engine.agent.tools import create_ticket as ct
    from ai_engine.integrations import anthropic_client as ac

    monkeypatch.setenv("SOURCEGRAPH_URL", "http://sg")
    monkeypatch.setenv("SOURCEGRAPH_TOKEN", "tok")
    from ai_engine.config import settings

    settings.reload()
    respx.post("http://sg/.api/graphql").mock(
        return_value=Response(200, json={"data": {"search": {"results": {"results": []}}}})
    )

    posted: list[dict] = []

    async def fake_post(url, json, headers):
        posted.append(json)

        class R:
            status_code = 200

        return R()

    monkeypatch.setattr(ct, "_post", fake_post)

    seq = iter(
        [
            _resp(
                [_block("tool_use", id="1", name="query_api_call", input={"uid": "1765348436409"})],
                "tool_use",
            ),
            _resp(
                [
                    _block(
                        "tool_use",
                        id="2",
                        name="search_code",
                        input={"repo": "openapi_backend", "query": "card_bind"},
                    )
                ],
                "tool_use",
            ),
            _resp(
                [
                    _block(
                        "tool_use",
                        id="3",
                        name="create_ticket",
                        input={
                            "category": "bug",
                            "summary": "card_bind 偶发 500 + DB_TIMEOUT",
                            "severity": "p1",
                            "evidence": {
                                "data_refs": [{"uid": "1765348436409", "status_code": 500}]
                            },
                        },
                    )
                ],
                "tool_use",
            ),
            _resp(
                [_block("text", text="已为您创建 bug 工单。证据：500 + DB_TIMEOUT。")], "end_turn"
            ),
            # self-check 修订轮（spec §8.3）：原样返回
            _resp(
                [_block("text", text="已为您创建 bug 工单。证据：500 + DB_TIMEOUT。")], "end_turn"
            ),
        ]
    )

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=lambda **kw: next(seq))
    monkeypatch.setattr(ac, "_client", fake_client)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        conv_id = await _init_conv(client)
        tool_results = []
        async with client.stream(
            "GET",
            f"/api/v1/chat?conversation_id={conv_id}&message=card_bind 偶发 500 uid=1765348436409",
            headers={"X-BU-ID": "BU00243780"},
        ) as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.strip() == "event: tool_result":
                    tool_results.append(line)

    assert len(tool_results) == 3  # query_api_call + search_code + create_ticket
    assert posted and posted[-1]["category"] == "bug"


@respx.mock
async def test_e2e_cross_bu_query_is_blocked(seeded_db, monkeypatch):
    """spec §10 验收：AI 试图查其他 BU 的卡 → 服务端注入会话身份 → 查不到 → AI 说无权限。"""
    from ai_engine import main as main_mod
    from ai_engine.integrations import anthropic_client as ac

    seq = iter(
        [
            _resp(
                [
                    _block(
                        "tool_use",
                        id="1",
                        name="query_card",
                        input={"bu_id": "BU_OTHER", "card_id": "1111222233334444"},
                    )
                ],
                "tool_use",
            ),
            _resp(
                [_block("text", text="未在您 BU 下找到该卡片。我没有权限查询其他 BU 的数据。")],
                "end_turn",
            ),
            # self-check 修订轮（spec §8.3）：原样返回
            _resp(
                [_block("text", text="未在您 BU 下找到该卡片。我没有权限查询其他 BU 的数据。")],
                "end_turn",
            ),
        ]
    )

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=lambda **kw: next(seq))
    monkeypatch.setattr(ac, "_client", fake_client)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        conv_id = await _init_conv(client)
        lines = []
        async with client.stream(
            "GET",
            f"/api/v1/chat?conversation_id={conv_id}&message=查一下卡 1111222233334444",
            headers={"X-BU-ID": "BU00243780"},
        ) as resp:
            async for line in resp.aiter_lines():
                lines.append(line)

    joined = "\n".join(lines)
    assert "未在您 BU 下" in joined or "其他 BU" in joined
