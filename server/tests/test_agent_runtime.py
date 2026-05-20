from unittest.mock import AsyncMock, MagicMock

import respx
from httpx import Response


@respx.mock
async def test_runtime_runs_tool_then_replies(seeded_db, monkeypatch):
    """模拟：第一次模型返回 tool_use(search_code)；第二次返回纯文本。"""
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac

    # search_code 走 Sourcegraph，用 respx mock 返回空结果（避免真实 HTTP）
    monkeypatch.setenv("SOURCEGRAPH_URL", "http://sg")
    monkeypatch.setenv("SOURCEGRAPH_TOKEN", "tok")
    from ai_engine.config import settings

    settings.reload()
    respx.post("http://sg/.api/graphql").mock(
        return_value=Response(200, json={"data": {"search": {"results": {"results": []}}}})
    )

    call_seq = []

    class FakeResp:
        def __init__(self, blocks, stop_reason):
            self.content = blocks
            self.stop_reason = stop_reason
            self.usage = MagicMock(input_tokens=10, output_tokens=10)

    async def fake_create(**kwargs):
        call_seq.append(kwargs)
        if len(call_seq) == 1:
            # 注意：MagicMock(name=...) 是构造器保留参数（设 mock repr 名），
            # 不会设成 .name 属性，必须事后赋值
            tu = MagicMock(
                type="tool_use",
                id="t1",
                input={"repo": "openapi_backend", "query": "card_bind"},
            )
            tu.name = "search_code"
            return FakeResp([tu], "tool_use")
        return FakeResp(
            [
                MagicMock(
                    type="text", text="结论：handler 在 card_bind.py。证据：search_code 命中。"
                )
            ],
            "end_turn",
        )

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=fake_create)
    monkeypatch.setattr(ac, "_client", fake_client)

    chunks = []
    async for ev in runtime.run_turn(
        conversation_id=1,
        user_type="b",
        subject_id="BU00243780",
        user_message="card_bind 接口 500 怎么回事？",
    ):
        chunks.append(ev)

    kinds = [c["type"] for c in chunks]
    assert "tool_call" in kinds
    assert "text" in kinds
    assert "结论" in "".join(c.get("text", "") for c in chunks if c["type"] == "text")
