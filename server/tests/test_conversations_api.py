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


async def test_conversations_init_rejects_no_bu(seeded_db):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/conversations", json={})
    assert resp.status_code == 401
