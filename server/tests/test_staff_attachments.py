from httpx import ASGITransport, AsyncClient

from ai_engine.persistence import attachments as att_dao
from ai_engine.storage import object_store as om

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class _FakeStore:
    def __init__(self):
        self.data = {}

    async def put(self, k, d, c):
        self.data[k] = d

    async def get(self, k):
        return b"x"

    async def presigned_get(self, k, t):
        return "https://signed.example/x"


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _setup_taken_conv(staff_sub: str) -> int:
    from ai_engine.persistence.conversations import create_conversation, set_mode

    cid = await create_conversation("c", "u-1")
    await set_mode(cid, "human_takeover", staff_sub)
    return cid


async def test_staff_upload_and_send_with_attachment(seeded_db):
    om.set_object_store(_FakeStore())
    from ai_engine import main as main_mod
    from ai_engine.auth.staff_session import issue_staff_token

    token = issue_staff_token("AG1", "agent")
    cid = await _setup_taken_conv("AG1")

    async with AsyncClient(
        transport=ASGITransport(app=main_mod.app), base_url="http://test"
    ) as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files={"file": ("s.png", PNG, "image/png")},
            headers=_h(token),
        )
        assert r.status_code == 200
        aid = r.json()["attachment_id"]

        r2 = await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "给你截图", "attachment_ids": [aid]},
            headers=_h(token),
        )
        assert r2.status_code == 200

    rows = await att_dao.list_for_conversation(cid)
    assert any(aid == a["id"] for atts in rows.values() for a in atts)


async def test_staff_send_image_only_allowed(seeded_db):
    om.set_object_store(_FakeStore())
    from ai_engine import main as main_mod
    from ai_engine.auth.staff_session import issue_staff_token

    token = issue_staff_token("AG2", "agent")
    cid = await _setup_taken_conv("AG2")

    async with AsyncClient(
        transport=ASGITransport(app=main_mod.app), base_url="http://test"
    ) as client:
        up = await client.post(
            f"/staff/api/v1/conversations/{cid}/attachments",
            files={"file": ("s.png", PNG, "image/png")},
            headers=_h(token),
        )
        aid = up.json()["attachment_id"]
        # 纯图片（content 空）也允许发送
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "", "attachment_ids": [aid]},
            headers=_h(token),
        )
        assert r.status_code == 200
