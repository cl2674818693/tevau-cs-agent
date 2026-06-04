import pytest

from ai_engine.persistence import rbac
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    rbac.invalidate_cache()
    yield temp_db_url
    rbac.invalidate_cache()


@pytest.mark.asyncio
async def test_chat_dispatch_default_matrix(db_ready):
    rbac.invalidate_cache()
    assert await rbac.is_permitted("agent", "chat.dispatch") is True
    assert await rbac.is_permitted("senior", "chat.dispatch") is True
    assert await rbac.is_permitted("supervisor", "chat.dispatch") is True
    assert await rbac.is_permitted("engineer", "chat.dispatch") is False
    assert await rbac.is_permitted("manager", "chat.dispatch") is False
    assert await rbac.is_permitted("admin", "chat.dispatch") is True


@pytest.mark.asyncio
async def test_chat_dispatch_in_permission_keys():
    assert "chat.dispatch" in rbac.PERMISSION_KEYS
    assert "admin.shifts" not in rbac.PERMISSION_KEYS  # 同时确认旧 key 已删
