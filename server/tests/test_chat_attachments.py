from httpx import ASGITransport, AsyncClient

from ai_engine.storage import object_store as om

BU = "BU00243780"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class _FakeStore:
    def __init__(self):
        self.data = {}

    async def put(self, k, d, c):
        self.data[k] = d

    async def get(self, k):
        return self.data[k]

    async def presigned_get(self, k, t):
        return f"https://signed.example/{k}"


async def test_chat_passes_attachment_ids_to_run_turn(seeded_db, monkeypatch):
    """chat 端点把 attachment_ids 透传给 run_turn（绑定/注入在 run_turn 内，见 Task7）。"""
    om.set_object_store(_FakeStore())
    from ai_engine import main as main_mod
    from ai_engine.agent import runtime

    seen: dict = {}

    async def fake_run_turn(**kwargs):
        seen.update(kwargs)
        yield {"type": "text", "text": "ok"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    async with AsyncClient(
        transport=ASGITransport(app=main_mod.app), base_url="http://test"
    ) as client:
        init = await client.post("/api/v1/conversations", json={}, headers={"X-BU-ID": BU})
        conv_id = init.json()["conversation_id"]
        # 先上传一张图
        up = await client.post(
            f"/api/v1/conversations/{conv_id}/attachments",
            files={"file": ("a.png", PNG, "image/png")},
            headers={"X-BU-ID": BU},
        )
        aid = up.json()["attachment_id"]
        async with client.stream(
            "GET",
            f"/api/v1/chat?conversation_id={conv_id}&message=hi&attachment_ids={aid}",
            headers={"X-BU-ID": BU},
        ) as resp:
            assert resp.status_code == 200
            [_ async for _ in resp.aiter_lines()]

    assert seen.get("attachment_ids") == [aid]
