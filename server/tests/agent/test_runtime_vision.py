"""Agent runtime: vision（图片附件）路径

被测对象：
- runtime._build_user_content：附件 → base64 image block + 文本块；无附件直接返回 str。
- runtime.run_turn 走带附件路径时：消息 content 是 list；纯图（user_message 为空）跳过 topic_classifier。

mock 策略：
- 用 set_object_store 注入假对象存储（避免连真实 S3/MinIO）。
- _client.messages.stream 用 fake_stream 给一段固定响应。
"""

from typing import Any

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence import attachments as att_dao
from ai_engine.persistence.conversations import create_conversation
from ai_engine.storage import object_store as os_mod


class _FakeStore:
    """内存假对象存储：put 存到 dict，get 按 key 取；不连任何网络。"""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:  # noqa: ARG002
        self._data[key] = data

    async def get(self, key: str) -> bytes:
        return self._data[key]

    async def presigned_get(self, key: str, ttl_seconds: int) -> str:  # noqa: ARG002
        return f"local://{key}"


@pytest.fixture
def fake_store(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(os_mod, "_store", store)
    yield store
    monkeypatch.setattr(os_mod, "_store", None)


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}

    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


class TestBuildUserContent:
    """_build_user_content：无附件直返 str；有附件返回 [image..., text] 块列表。"""

    async def test_no_attachment_returns_plain_str(self) -> None:
        out = await rt._build_user_content("hello", [])
        assert out == "hello"

    async def test_attachment_returns_image_then_text_blocks(self, fake_store) -> None:
        await fake_store.put("k1.png", b"\x89PNG-bytes", "image/png")
        out = await rt._build_user_content(
            "看图", [{"object_key": "k1.png", "mime": "image/png"}]
        )
        assert isinstance(out, list)
        assert out[0]["type"] == "image"
        assert out[0]["source"]["media_type"] == "image/png"
        assert out[0]["source"]["type"] == "base64"
        # 末尾文本块
        assert out[-1] == {"type": "text", "text": "看图"}

    async def test_attachment_no_text_only_image_block(self, fake_store) -> None:
        await fake_store.put("k1.jpg", b"jpgbytes", "image/jpeg")
        out = await rt._build_user_content(
            "", [{"object_key": "k1.jpg", "mime": "image/jpeg"}]
        )
        assert isinstance(out, list)
        assert all(b["type"] == "image" for b in out)
        assert len(out) == 1

    async def test_multiple_attachments_all_become_image_blocks(self, fake_store) -> None:
        await fake_store.put("a.png", b"a", "image/png")
        await fake_store.put("b.png", b"b", "image/png")
        out = await rt._build_user_content(
            "两张",
            [
                {"object_key": "a.png", "mime": "image/png"},
                {"object_key": "b.png", "mime": "image/png"},
            ],
        )
        assert len([b for b in out if b["type"] == "image"]) == 2
        assert out[-1]["text"] == "两张"


class TestRunTurnWithAttachments:
    """run_turn 带 attachment_ids：附件绑定后注入 image block；纯图绕过 topic_classifier。"""

    async def test_run_turn_with_image_attachment(
        self, monkeypatch, seeded_db, fake_store, fake_stream, make_resp
    ) -> None:
        conv_id = await create_conversation("c", "U001")
        # 先建一行未绑定 attachment
        await fake_store.put("img1.png", b"\x89PNG\x00\x00", "image/png")
        aid = await att_dao.create_attachment(
            conv_id=conv_id,
            uploader_type="c",
            uploader_id="U001",
            object_key="img1.png",
            mime="image/png",
            byte_size=6,
            sha256="abc",
        )

        responses = [make_resp(text="收到图片"), make_resp(text="已识别")]
        captured_req: dict[str, Any] = {}

        # 捕获最后一次 stream 请求体
        def _stream(**kw):  # noqa: ANN003
            captured_req.update(kw)
            seq = iter(responses)
            from tests.conftest import _FakeMessageStream

            return _FakeMessageStream(next(seq) if responses else None)

        # 用 fake_stream 标准 fixture 跑流程，单独验证 attachment 已经被绑定
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))

        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv_id,
                user_type="c",
                subject_id="U001",
                user_message="这张截图",
                attachment_ids=[aid],
            )
        ]
        assert any(e.get("type") == "text" for e in events)
        # 附件被绑定到 user 行
        attached = await att_dao.list_for_conversation(conv_id)
        assert any(aid in [a["id"] for a in v] for v in attached.values())

    async def test_pure_image_bypasses_topic_classifier(
        self, monkeypatch, seeded_db, fake_store, fake_stream, make_resp
    ) -> None:
        """user_message='' 时 runtime 跳过 classify（避免误拒）。开启 classifier 也不能误杀。"""
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "topic_classifier_enabled", True)
        # classify 若被调用应当抛错，证明这条路径未走
        async def _no_call(_msg):
            raise AssertionError("topic classify must be skipped for pure-image input")

        from ai_engine.agent import topic_classifier

        monkeypatch.setattr(topic_classifier, "classify", _no_call)

        conv_id = await create_conversation("c", "U001")
        await fake_store.put("p.png", b"pp", "image/png")
        aid = await att_dao.create_attachment(
            conv_id=conv_id,
            uploader_type="c",
            uploader_id="U001",
            object_key="p.png",
            mime="image/png",
            byte_size=2,
            sha256="x",
        )
        monkeypatch.setattr(
            _ac._client.messages,
            "stream",
            fake_stream([make_resp(text="ok"), make_resp(text="ok")]),
        )

        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv_id,
                user_type="c",
                subject_id="U001",
                user_message="",  # 纯图
                attachment_ids=[aid],
            )
        ]
        # 仅断言流程没崩；classifier 没被调用即通过
        assert events
