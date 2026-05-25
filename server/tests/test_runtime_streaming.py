"""真 token 流式（spec §10 / MVP-3）：最终回复按增量实时流出，按换行边界做流式脱敏。

要点：
- 自检前的草稿轮不流出（被 self-check 修订）；自检后的最终回复才逐段流出。
- PII 即使被切到多个增量里，只要在同一行内，按整行 redact 后仍安全（不漏脱）。
"""

from unittest.mock import MagicMock


def _block(text: str) -> MagicMock:
    return MagicMock(type="text", text=text)


def _resp(text: str, stop: str = "end_turn") -> MagicMock:
    return MagicMock(
        content=[_block(text)],
        stop_reason=stop,
        usage=MagicMock(input_tokens=1, output_tokens=1),
    )


class _ChunkedStream:
    """把整段回复切成多个增量来模拟真实 token 流；get_final_message 返回完整消息。"""

    def __init__(self, chunks: list[str]):
        self._chunks = chunks
        self._full = "".join(chunks)

    async def __aenter__(self) -> "_ChunkedStream":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    @property
    def text_stream(self):  # type: ignore[no-untyped-def]
        async def _gen():  # type: ignore[no-untyped-def]
            for c in self._chunks:
                yield c

        return _gen()

    async def get_final_message(self) -> MagicMock:
        return _resp(self._full)


async def test_final_reply_streams_in_multiple_deltas_and_redacts(seeded_db, monkeypatch):
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac

    # 手机号被切成 3 段（同一行），卡号带空格分隔（跨空格）；都应被脱敏。
    chunks = ["您的手机 138", "1234", "5678 已解绑\n", "卡号 4938 7506 7246 4590 完成"]
    calls = {"n": 0}

    def _stream(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            # 第一轮（草稿）：返回一段会被 self-check 修订的草稿
            return _ChunkedStream(["草稿，不应流给用户\n"])
        return _ChunkedStream(chunks)

    fake = MagicMock()
    fake.messages.stream = MagicMock(side_effect=_stream)
    monkeypatch.setattr(ac, "_client", fake)

    texts = [
        ev["text"]
        async for ev in runtime.run_turn(
            conversation_id=1, user_type="b", subject_id="BU00243780", user_message="hi"
        )
        if ev["type"] == "text"
    ]

    joined = "".join(texts)
    # 多段流出（真流式）：最终回复不止一个 text 事件
    assert len(texts) >= 2
    # 草稿轮的内容被吞掉
    assert "草稿" not in joined
    # PII 脱敏（即使被切到多个增量）
    assert "13812345678" not in joined
    assert "4938 7506 7246 4590" not in joined
    assert "已解绑" in joined and "完成" in joined
