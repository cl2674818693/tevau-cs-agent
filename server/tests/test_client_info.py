"""会话客户端信息：H5 上报 + admin 查询。

不连业务库（unlimitpay）的场景下，subject-info 应该仍返回 client_info，
subject.found=False 不阻断响应。
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def staff_token(temp_db_url, monkeypatch):
    monkeypatch.setenv("STAFF_SESSION_SECRET", "test-staff-secret")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token

    return issue_staff_token("admin", "admin")


async def _seed_conv(user_type: str = "c", subject_id: str = "U1") -> int:
    from ai_engine.persistence import db
    from ai_engine.persistence.schema import now_str

    return await db.insert_returning_id(
        "INSERT INTO conversations(user_type, subject_id, created_at) "
        "VALUES (:ut, :sid, :now) RETURNING id",
        {"ut": user_type, "sid": subject_id, "now": now_str()},
    )


async def test_upsert_and_get_client_info(temp_db_url):
    from ai_engine.persistence import client_info as ci
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await _seed_conv()
    await ci.upsert_client_info(cid, "ios", "1.2.3", "Mozilla/5.0 (iPhone)")
    row = await ci.get_client_info(cid)
    assert row is not None
    assert row["platform"] == "ios"
    assert row["app_version"] == "1.2.3"
    assert "iPhone" in row["user_agent"]

    # upsert 覆盖
    await ci.upsert_client_info(cid, "android", "2.0.0", "Mozilla/5.0 (Linux; Android)")
    row = await ci.get_client_info(cid)
    assert row["platform"] == "android"
    assert row["app_version"] == "2.0.0"


async def test_get_client_info_missing(temp_db_url):
    from ai_engine.persistence import client_info as ci
    from ai_engine.persistence.db import init_db

    await init_db()
    assert await ci.get_client_info(999999) is None


async def test_subject_info_endpoint_no_business_db(temp_db_url, staff_token, monkeypatch):
    """业务库未配置时（dev/test 默认），subject.found=False 但 client_info 应能返回。"""
    monkeypatch.setenv("UNLIMITPAY_DB_URL", "")
    monkeypatch.setenv("NEXUS_DB_URL", "")
    from ai_engine.config import settings
    from ai_engine.persistence import client_info as ci
    from ai_engine.persistence.db import init_db

    settings.reload()
    await init_db()
    cid = await _seed_conv(user_type="c", subject_id="U1")
    await ci.upsert_client_info(cid, "ios", "1.0.0", "ua-test")

    from ai_engine.main import app

    with TestClient(app) as client:
        r = client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info",
            headers={"Authorization": f"Bearer {staff_token}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subject"]["user_type"] == "c"
    assert body["subject"]["found"] is False
    assert body["client_info"]["platform"] == "ios"
    assert body["client_info"]["app_version"] == "1.0.0"


async def test_subject_info_endpoint_404(temp_db_url, staff_token):
    from ai_engine.main import app
    from ai_engine.persistence.db import init_db

    await init_db()
    with TestClient(app) as client:
        r = client.get(
            "/staff/api/v1/conversations/999999/subject-info",
            headers={"Authorization": f"Bearer {staff_token}"},
        )
    assert r.status_code == 404
