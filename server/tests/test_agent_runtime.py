from unittest.mock import MagicMock

import respx
from httpx import Response


@respx.mock
async def test_runtime_runs_tool_then_replies(seeded_db, monkeypatch, fake_stream):
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
    fake_client.messages.stream = fake_stream(fake_create)
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


async def test_run_tools_events_carry_result_count_and_empty(monkeypatch):
    """旁观需要看到工具返回条数/空标记，否则'查空'在旁观里看不出。"""
    from ai_engine.agent import runtime
    from ai_engine.agent.cost_guard import CostGuard

    async def fake_dispatch(*, tool_name, params, user_type, subject_id, conversation_id):
        if tool_name == "has_rows":
            return {"ok": True, "data": {"rows": [{"a": 1}, {"a": 2}, {"a": 3}]}}
        if tool_name == "empty_rows":
            return {"ok": True, "data": {"rows": []}}
        return {"ok": False, "error": "boom"}

    monkeypatch.setattr(runtime, "dispatch", fake_dispatch)

    guard = CostGuard(max_depth=10, max_result_bytes=100000)
    tool_calls = [
        {"id": "a", "name": "has_rows", "input": {}},
        {"id": "b", "name": "empty_rows", "input": {}},
        {"id": "c", "name": "fail", "input": {}},
    ]
    _blocks, events = await runtime._run_tools(
        tool_calls, guard, user_type="b", subject_id="BU1", conversation_id=1
    )

    by_id = {e["id"]: e for e in events}
    assert by_id["a"]["result_count"] == 3
    assert by_id["a"]["empty"] is False
    assert by_id["b"]["result_count"] == 0
    assert by_id["b"]["empty"] is True
    assert by_id["c"]["ok"] is False
    assert by_id["c"]["result_count"] == 0
    assert by_id["c"]["empty"] is True
