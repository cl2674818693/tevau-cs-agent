"""Agent runtime: 历史回放

被测对象：
- runtime._load_history：把 messages 表还原为 Anthropic messages（含 user/assistant/human_agent；
  ai_draft/system 跳过；带附件 user 行回灌 base64 image block）。
- runtime._coalesce：相邻同 role 纯文本拼接；图片块（list）不合并。
- runtime._detect_locale：语言粗判矩阵。
- persistence.message_content_text：assistant content json→text。

注：runtime 中没有名为 history_replay 的独立模块；历史回放分散在 runtime._load_history 与
persistence.conversations.message_content_text。本文件覆盖这两条路径。
"""

import json

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.persistence import attachments as att_dao
from ai_engine.persistence.conversations import (
    append_human_message,
    append_message,
    create_conversation,
    message_content_text,
    save_ai_draft,
)
from ai_engine.storage import object_store as os_mod


class _FakeStore:
    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    async def put(self, key, data, ct):  # noqa: ANN001,ARG002
        self._data[key] = data

    async def get(self, key):  # noqa: ANN001
        return self._data[key]

    async def presigned_get(self, key, ttl):  # noqa: ANN001,ARG002
        return f"local://{key}"


@pytest.fixture
def fake_store(monkeypatch):
    s = _FakeStore()
    monkeypatch.setattr(os_mod, "_store", s)
    yield s
    monkeypatch.setattr(os_mod, "_store", None)


class TestMessageContentText:
    """assistant 写入是 json blocks；其它角色原样回。"""

    def test_user_role_returns_raw(self) -> None:
        assert message_content_text("user", "hello") == "hello"

    def test_human_agent_returns_raw(self) -> None:
        assert message_content_text("human_agent", "by staff") == "by staff"

    def test_assistant_json_blocks_concatenated(self) -> None:
        blob = json.dumps(
            [{"type": "text", "text": "A"}, {"type": "text", "text": "B"}]
        )
        assert message_content_text("assistant", blob) == "AB"

    def test_assistant_non_json_returns_raw(self) -> None:
        # 历史灰度可能存了非 json 字符串；不应 crash
        assert message_content_text("assistant", "plain text") == "plain text"

    def test_assistant_non_list_json_returns_raw(self) -> None:
        assert message_content_text("assistant", '{"a":1}') == '{"a":1}'

    def test_assistant_skips_non_text_blocks(self) -> None:
        blob = json.dumps(
            [{"type": "text", "text": "X"}, {"type": "tool_use", "name": "q"}]
        )
        assert message_content_text("assistant", blob) == "X"


class TestDetectLocale:
    """_detect_locale 区段优先级。"""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("안녕하세요", "ko"),  # Hangul
            ("こんにちは", "ja"),  # 平假名
            ("カタカナ", "ja"),  # 片假名
            ("สวัสดี", "th"),  # Thai
            ("你好世界", "zh"),  # CJK
            ("hello world", "en"),  # 纯 ASCII 字母
            ("12345", None),  # 纯数字 → None
            ("!?!?", None),  # 纯标点
            ("", None),  # 空
        ],
    )
    def test_locale_matrix(self, text: str, expected: str | None) -> None:
        assert rt._detect_locale(text) == expected

    def test_mixed_cjk_wins_over_latin(self) -> None:
        # 含中文 → zh，不会被 latin 误判
        assert rt._detect_locale("hello 你好") == "zh"


class TestCoalesce:
    """_coalesce 合并相邻同 role 文本；图片块（list content）独立。"""

    def test_merge_two_user_strings(self) -> None:
        out = rt._coalesce(
            [
                {"role": "user", "content": "a"},
                {"role": "user", "content": "b"},
            ]
        )
        assert out == [{"role": "user", "content": "a\nb"}]

    def test_no_merge_alternate_roles(self) -> None:
        out = rt._coalesce(
            [
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
                {"role": "user", "content": "c"},
            ]
        )
        assert len(out) == 3

    def test_no_merge_when_image_blocks(self) -> None:
        # list content 是图片块，不与 str content 合并
        out = rt._coalesce(
            [
                {"role": "user", "content": "a"},
                {"role": "user", "content": [{"type": "image"}]},
            ]
        )
        assert len(out) == 2

    def test_does_not_mutate_input(self) -> None:
        src = [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]
        rt._coalesce(src)
        # 原列表元素未被改
        assert src[0]["content"] == "a"


class TestLoadHistory:
    """_load_history：从 messages 表回放成 Anthropic messages 列表。"""

    async def test_skip_system_and_ai_draft(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        await append_message(conv, role="user", content="hi")
        await append_message(conv, role="system", content="ignored summary")
        await save_ai_draft(conv, content="ignored draft")
        await append_message(
            conv,
            role="assistant",
            content=json.dumps([{"type": "text", "text": "hello"}]),
        )

        out = await rt._load_history(conv)
        roles = [m["role"] for m in out]
        assert "system" not in roles
        # ai_draft 不应进入历史
        assert all("ignored draft" not in str(m["content"]) for m in out)
        # assistant 内容被还原
        assistant_msgs = [m for m in out if m["role"] == "assistant"]
        assert assistant_msgs[0]["content"] == "hello"

    async def test_human_agent_treated_as_assistant(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        await append_message(conv, role="user", content="ask")
        await append_human_message(conv, sender_staff_id="staff1", content="by human")
        out = await rt._load_history(conv)
        # human_agent 在历史里被映射成 assistant 角色（让 LLM 看到客服话）
        assert any(m["role"] == "assistant" and m["content"] == "by human" for m in out)

    async def test_attachments_reinjected_as_image_block(
        self, seeded_db, fake_store
    ) -> None:
        conv = await create_conversation("c", "U001")
        msg_id = await append_message(conv, role="user", content="看这个")
        # 建附件并直接绑定到该 message
        await fake_store.put("k.png", b"PNGBYTES", "image/png")
        aid = await att_dao.create_attachment(
            conv_id=conv,
            uploader_type="c",
            uploader_id="U001",
            object_key="k.png",
            mime="image/png",
            byte_size=8,
            sha256="x",
        )
        await att_dao.bind_attachments(msg_id, conv, "U001", [aid])

        out = await rt._load_history(conv)
        user = next(m for m in out if m["role"] == "user")
        # content 应为 list（含 image + text）
        assert isinstance(user["content"], list)
        assert user["content"][0]["type"] == "image"

    async def test_empty_conversation_returns_empty(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        assert await rt._load_history(conv) == []
