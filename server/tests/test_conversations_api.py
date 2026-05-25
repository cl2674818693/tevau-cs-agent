from httpx import ASGITransport, AsyncClient


async def test_conversations_init_returns_user_type_b(seeded_db):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/conversations", json={}, headers={"X-BU-ID": "BU00243780"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_type"] == "b"
    assert body["conversation_id"]
    assert body["display_name"]
    assert body["greeting"]
    assert "limits" in body


async def test_conversations_init_falls_back_to_guest(seeded_db):
    """无 cookie / 无 X-BU-ID / 无 Bearer → 降级游客会话（user_type=g），不再 401。"""
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/conversations", json={})
    assert resp.status_code == 200
    assert resp.json()["user_type"] == "g"
