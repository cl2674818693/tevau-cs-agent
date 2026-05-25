from httpx import ASGITransport, AsyncClient

_H = {"X-BU-ID": "BU00243780"}


async def test_submit_feedback_persists_and_counts(seeded_db):
    from ai_engine import main as main_mod
    from ai_engine.persistence import db

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        init = await client.post("/api/v1/conversations", json={}, headers=_H)
        cid = init.json()["conversation_id"]
        r = await client.post(
            f"/api/v1/conversations/{cid}/feedback",
            json={"message_id": 1, "rating": "down", "reason": "答非所问"},
            headers=_H,
        )
    assert r.status_code == 200
    rows = await db.fetch_all(
        "SELECT rating, reason FROM message_feedback WHERE conversation_id=:c", {"c": cid}
    )
    assert rows and rows[0]["rating"] == "down"
    assert rows[0]["reason"] == "答非所问"


async def test_feedback_rejects_bad_rating(seeded_db):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        init = await client.post("/api/v1/conversations", json={}, headers=_H)
        cid = init.json()["conversation_id"]
        r = await client.post(
            f"/api/v1/conversations/{cid}/feedback",
            json={"message_id": 1, "rating": "meh"},
            headers=_H,
        )
    assert r.status_code == 400


async def test_feedback_rejects_cross_identity(seeded_db):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        init = await client.post("/api/v1/conversations", json={}, headers=_H)
        cid = init.json()["conversation_id"]
        r = await client.post(
            f"/api/v1/conversations/{cid}/feedback",
            json={"message_id": 1, "rating": "up"},
            headers={"X-BU-ID": "BU_OTHER"},
        )
    assert r.status_code == 403
