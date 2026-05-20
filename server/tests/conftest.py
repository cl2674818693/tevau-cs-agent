import os
import tempfile

import pytest


@pytest.fixture
def temp_db_url(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DB_URL", url)
    from ai_engine.config import settings

    settings.reload()
    yield url
    os.remove(path)
