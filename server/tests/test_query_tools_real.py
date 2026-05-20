import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pytest


def _docker_ok() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=8)  # noqa: S607
        return r.returncode == 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _docker_ok(), reason="docker not available")


@pytest.fixture(scope="module")
def mysql_url():
    from testcontainers.mysql import MySqlContainer

    with MySqlContainer("mysql:8.0") as mysql:
        raw = mysql.get_connection_url().replace("mysql+pymysql://", "mysql://")
        import pymysql

        p = urlparse(raw)
        conn = pymysql.connect(
            host=p.hostname,
            port=p.port or 3306,
            user=p.username,
            password=p.password,
            database=(p.path or "").lstrip("/"),
        )
        try:
            sql = Path("tests/fixtures/unlimitpay_seed.sql").read_text(encoding="utf-8")
            with conn.cursor() as cur:
                for stmt in sql.split(";"):
                    if stmt.strip():
                        cur.execute(stmt)
            conn.commit()
        finally:
            conn.close()
        yield raw


@pytest.fixture(autouse=True)
async def _init(monkeypatch, mysql_url):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("UNLIMITPAY_DB_URL", mysql_url)
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.persistence import business_db

    await business_db.init_business_dbs(mysql_url, None)
    yield
    await business_db.close_all()


async def test_query_user_returns_masked_data():
    from ai_engine.agent.tools.query_user import run

    out = await run(bu_id="BU00243780", user_id="U1")
    u = out["user"]
    assert u["email"] == "al***@x.com"
    assert u["phone"] == "138****78"
    assert u["bu_id"] == "BU00243780"


async def test_query_user_rejects_cross_bu():
    from ai_engine.agent.tools.query_user import run

    out = await run(bu_id="BU00243780", user_id="U2")  # U2 属于 BU_OTHER
    assert out["user"] is None


async def test_query_card_masks_card_no_and_lock_reason():
    from ai_engine.agent.tools.query_card import run

    out = await run(bu_id="BU00243780", card_id="C100")
    c = out["card"]
    assert "R-217" not in c["lock_reason"]
    assert c["card_no"] == "4938 **** **** 4590"


async def test_query_api_call_by_uid():
    from ai_engine.agent.tools.query_api_call import run

    out = await run(bu_id="BU00243780", uid="1765348436409")
    assert out["call"]["status_code"] == 500
