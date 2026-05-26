import base64

from ai_engine.agent import runtime
from ai_engine.storage import object_store as om


class _FakeStore:
    async def put(self, k, d, c): ...
    async def get(self, key):
        return b"IMGBYTES"

    async def presigned_get(self, k, t):
        return "x"


async def test_build_user_content_with_image_block():
    om.set_object_store(_FakeStore())
    atts = [{"id": 1, "object_key": "uploads/a.png", "mime": "image/png"}]
    content = await runtime._build_user_content("看这张", atts)
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/png"
    assert content[0]["source"]["data"] == base64.b64encode(b"IMGBYTES").decode()
    assert content[-1] == {"type": "text", "text": "看这张"}


async def test_build_user_content_no_attachments_is_plain_text():
    assert await runtime._build_user_content("hi", []) == "hi"


async def test_build_user_content_image_only_omits_text_block():
    om.set_object_store(_FakeStore())
    atts = [{"id": 1, "object_key": "uploads/a.png", "mime": "image/png"}]
    content = await runtime._build_user_content("", atts)
    assert len(content) == 1
    assert content[0]["type"] == "image"


def test_coalesce_does_not_merge_list_content():
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "a"}]},
        {"role": "user", "content": "b"},
    ]
    out = runtime._coalesce(msgs)
    # list content 不做字符串拼接，保持独立两条
    assert len(out) == 2


def test_coalesce_still_merges_adjacent_strings():
    msgs = [
        {"role": "assistant", "content": "a"},
        {"role": "assistant", "content": "b"},
    ]
    out = runtime._coalesce(msgs)
    assert len(out) == 1
    assert out[0]["content"] == "a\nb"
