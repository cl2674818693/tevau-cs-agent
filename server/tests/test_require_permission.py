import pytest
from fastapi import HTTPException

from ai_engine.auth.permission_dep import require_permission


async def test_allows_when_permitted(temp_db_url):
    from ai_engine.persistence import rbac
    from ai_engine.persistence.db import init_db
    await init_db()
    rbac.invalidate_cache()
    await rbac.upsert_many("AD1", [
        {"role": "agent", "permission_key": "test.feature", "allowed": 1},
    ])
    dep = require_permission("test.feature")
    out = await dep({"role": "agent"})
    assert out["role"] == "agent"


async def test_rejects_when_no_permission(temp_db_url):
    from ai_engine.persistence import rbac
    from ai_engine.persistence.db import init_db
    await init_db()
    rbac.invalidate_cache()
    dep = require_permission("test.feature")
    with pytest.raises(HTTPException) as e:
        await dep({"role": "agent"})
    assert e.value.status_code == 403


async def test_admin_default_has_all(temp_db_url):
    from ai_engine.persistence import rbac
    from ai_engine.persistence.db import init_db
    await init_db()
    rbac.invalidate_cache()
    dep = require_permission("admin.dashboard")
    out = await dep({"role": "admin"})
    assert out["role"] == "admin"
