import pytest


async def test_business_db_url(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("UNLIMITPAY_DB_URL", "mysql://u:p@h:3306/db")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.persistence.business_db import BusinessDB

    db = BusinessDB(settings.unlimitpay_db_url)
    assert db.url == "mysql://u:p@h:3306/db"


def test_parse_mysql_url():
    from ai_engine.persistence.business_db import parse_mysql_url

    cfg = parse_mysql_url("mysql://user:pass@host.example:3306/dbname")
    assert cfg == {
        "user": "user",
        "password": "pass",
        "host": "host.example",
        "port": 3306,
        "db": "dbname",
    }


def test_parse_mysql_url_rejects_invalid():
    from ai_engine.persistence.business_db import parse_mysql_url

    with pytest.raises(ValueError):
        parse_mysql_url("postgres://x")
