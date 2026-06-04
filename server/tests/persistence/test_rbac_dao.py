"""Persistence: rbac.py — 动态 RBAC：DB-first 覆盖默认矩阵 + 缓存。

覆盖：is_permitted（DB hit / DB miss 回退默认 / admin 全开 / agent 默认全关）,
list_matrix（合并 DB 与默认）, upsert_many（insert/update + 失效缓存）,
invalidate_cache。
"""

import pytest

from ai_engine.persistence import rbac
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    rbac.invalidate_cache()  # 每次测试开始清缓存
    yield temp_db_url
    rbac.invalidate_cache()


class TestDefaults:
    async def test_admin_has_all_perms(self, db_ready) -> None:
        for perm in rbac.PERMISSION_KEYS:
            assert await rbac.is_permitted("admin", perm) is True

    async def test_agent_has_chat_dispatch_only(self, db_ready) -> None:
        # agent 默认只有 chat.dispatch，无任何 admin.* 权限
        assert await rbac.is_permitted("agent", "chat.dispatch") is True
        admin_perms = [k for k in rbac.PERMISSION_KEYS if k.startswith("admin.")]
        for perm in admin_perms:
            assert await rbac.is_permitted("agent", perm) is False

    async def test_supervisor_dashboard_allowed(self, db_ready) -> None:
        assert await rbac.is_permitted("supervisor", "admin.dashboard") is True

    async def test_supervisor_rbac_denied(self, db_ready) -> None:
        # rbac 仅 admin
        assert await rbac.is_permitted("supervisor", "admin.rbac") is False

    async def test_unknown_role_denied(self, db_ready) -> None:
        assert await rbac.is_permitted("intern", "admin.dashboard") is False


class TestDbOverridesDefaults:
    async def test_db_allow_overrides_default_deny(self, db_ready) -> None:
        # agent 默认全关；设为 allow
        await rbac.upsert_many(
            "admin",
            [{"role": "agent", "permission_key": "admin.dashboard", "allowed": 1}],
        )
        assert await rbac.is_permitted("agent", "admin.dashboard") is True

    async def test_db_deny_overrides_default_allow(self, db_ready) -> None:
        # admin 默认全开；设为 deny
        await rbac.upsert_many(
            "admin",
            [{"role": "admin", "permission_key": "admin.dashboard", "allowed": 0}],
        )
        assert await rbac.is_permitted("admin", "admin.dashboard") is False


class TestUpsertMany:
    async def test_insert_then_update(self, db_ready) -> None:
        # 先 insert
        n1 = await rbac.upsert_many(
            "a", [{"role": "agent", "permission_key": "admin.dashboard", "allowed": 1}]
        )
        # 再 update（同 role/perm 走 UPDATE 分支）
        n2 = await rbac.upsert_many(
            "b", [{"role": "agent", "permission_key": "admin.dashboard", "allowed": 0}]
        )
        assert n1 == 1 and n2 == 1
        assert await rbac.is_permitted("agent", "admin.dashboard") is False

    async def test_batch(self, db_ready) -> None:
        items = [
            {"role": "agent", "permission_key": "admin.dashboard", "allowed": 1},
            {"role": "agent", "permission_key": "admin.staff", "allowed": 1},
        ]
        n = await rbac.upsert_many("a", items)
        assert n == 2

    async def test_cache_invalidated_after_upsert(self, db_ready) -> None:
        # 先读一次走 default（agent admin.dashboard 默认关），缓存进入
        assert await rbac.is_permitted("agent", "admin.dashboard") is False
        # upsert 应让下次读取看到新值
        await rbac.upsert_many(
            "a", [{"role": "agent", "permission_key": "admin.dashboard", "allowed": 1}]
        )
        assert await rbac.is_permitted("agent", "admin.dashboard") is True


class TestListMatrix:
    async def test_matrix_shape(self, db_ready) -> None:
        m = await rbac.list_matrix()
        assert set(m.keys()) == set(rbac.ROLES)
        for role in rbac.ROLES:
            assert set(m[role].keys()) == set(rbac.PERMISSION_KEYS)

    async def test_matrix_uses_defaults_when_db_empty(self, db_ready) -> None:
        m = await rbac.list_matrix()
        for perm in rbac.PERMISSION_KEYS:
            assert m["admin"][perm] is True
        # agent 默认：chat.dispatch=True，admin.* 全 False
        assert m["agent"]["chat.dispatch"] is True
        for perm in [k for k in rbac.PERMISSION_KEYS if k.startswith("admin.")]:
            assert m["agent"][perm] is False

    async def test_matrix_reflects_db_overrides(self, db_ready) -> None:
        await rbac.upsert_many(
            "a", [{"role": "agent", "permission_key": "admin.dashboard", "allowed": 1}]
        )
        m = await rbac.list_matrix()
        assert m["agent"]["admin.dashboard"] is True


class TestInvalidateCache:
    async def test_invalidate_clears(self, db_ready) -> None:
        await rbac.is_permitted("admin", "admin.dashboard")  # 预热
        rbac.invalidate_cache()
        # 再读应当从 DB 重新载入（无 error 即可）
        assert await rbac.is_permitted("admin", "admin.dashboard") is True
