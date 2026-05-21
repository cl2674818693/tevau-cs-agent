from unittest.mock import AsyncMock, MagicMock


def _block(type_: str, **kw):
    b = MagicMock(type=type_)
    for k, v in kw.items():
        setattr(b, k, v)
    return b


def _resp(blocks, stop_reason):
    r = MagicMock()
    r.content = blocks
    r.stop_reason = stop_reason
    r.usage = MagicMock(input_tokens=1, output_tokens=1)
    return r


async def test_self_check_injects_one_extra_round(seeded_db, monkeypatch):
    """end_turn 后强制注入一轮 self-check（spec §8.3），最终流出修订后的文本。"""
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac

    seq = iter(
        [
            _resp([_block("text", text="草稿：去看看代码吧。")], "end_turn"),
            _resp(
                [_block("text", text="修订：handler 在 card_bind.py，证据 search_code 命中。")],
                "end_turn",
            ),
        ]
    )
    fake = MagicMock()
    fake.messages.create = AsyncMock(side_effect=lambda **kw: next(seq))
    monkeypatch.setattr(ac, "_client", fake)

    texts = []
    async for ev in runtime.run_turn(
        conversation_id=1, user_type="b", subject_id="BU00243780", user_message="问题"
    ):
        if ev["type"] == "text":
            texts.append(ev["text"])

    joined = "".join(texts)
    # 草稿被吞掉，只流出修订稿
    assert "草稿" not in joined
    assert "修订" in joined
    # 调了两次模型：草稿 + self-check 修订
    assert fake.messages.create.await_count == 2
    # 第二次请求里带入了 self_check 提示（messages 是 live 引用，搜全量即可）
    second_req = fake.messages.create.await_args_list[1].kwargs
    assert any(
        m["role"] == "user" and isinstance(m["content"], str) and "审视" in m["content"]
        for m in second_req["messages"]
    )


async def test_self_check_skipped_when_no_text(seeded_db, monkeypatch):
    """end_turn 但无文本（罕见）：不注入 self-check，直接结束。"""
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac

    seq = iter([_resp([], "end_turn")])
    fake = MagicMock()
    fake.messages.create = AsyncMock(side_effect=lambda **kw: next(seq))
    monkeypatch.setattr(ac, "_client", fake)

    async for _ in runtime.run_turn(
        conversation_id=1, user_type="b", subject_id="BU00243780", user_message="问题"
    ):
        pass

    assert fake.messages.create.await_count == 1
