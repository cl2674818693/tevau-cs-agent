"""Persistence: staff.py — 账号 CRUD + 密码 hash/verify。

覆盖：hash_password (PBKDF2/legacy sha256) / verify_password 兼容,
create_staff (role 校验), authenticate (active=0 拒绝 / 错密码),
get_staff / list_staff / update_staff / set_staff_active / reset_staff_password。
"""

import hashlib

import pytest

from ai_engine.persistence import staff
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestHashAndVerifyPassword:
    """PBKDF2 格式 + 历史 sha256 二段格式兼容。"""

    def test_hash_format(self) -> None:
        h = staff.hash_password("pw", salt="ABC")
        parts = h.split("$")
        assert parts[0] == "pbkdf2"
        assert int(parts[1]) > 0
        assert parts[2] == "ABC"
        assert len(parts[3]) == 64  # sha256 hex

    def test_hash_uses_random_salt(self) -> None:
        a = staff.hash_password("pw")
        b = staff.hash_password("pw")
        assert a != b  # 随机 salt 应不同

    def test_verify_correct(self) -> None:
        h = staff.hash_password("pw")
        assert staff.verify_password("pw", h) is True

    def test_verify_wrong(self) -> None:
        h = staff.hash_password("pw")
        assert staff.verify_password("nope", h) is False

    def test_verify_legacy_sha256(self) -> None:
        """二段式 salt$sha256(salt+plain) 应兼容（历史数据）。"""
        salt = "abc"
        plain = "pw"
        legacy = f"{salt}${hashlib.sha256((salt + plain).encode()).hexdigest()}"
        assert staff.verify_password(plain, legacy) is True
        assert staff.verify_password("nope", legacy) is False

    def test_verify_unknown_format(self) -> None:
        assert staff.verify_password("pw", "garbage") is False


class TestCreateStaff:
    @pytest.mark.parametrize("role", ["agent", "senior", "engineer", "admin", "supervisor", "manager"])
    async def test_valid_roles(self, db_ready, role: str) -> None:
        sid = await staff.create_staff(f"staff-{role}", "Name", role, "pw")
        assert sid > 0

    async def test_invalid_role_raises(self, db_ready) -> None:
        with pytest.raises(ValueError):
            await staff.create_staff("staff-x", "Name", "intern", "pw")

    async def test_password_stored_hashed(self, db_ready) -> None:
        await staff.create_staff("staff-1", "Name", "agent", "secret")
        # 直接读 password_hash 验证非明文
        row = await staff.authenticate("staff-1", "secret")
        assert row is not None

    async def test_duplicate_staff_id_raises(self, db_ready) -> None:
        await staff.create_staff("staff-1", "Name", "agent", "pw")
        with pytest.raises(Exception):  # noqa: B017 unique 约束
            await staff.create_staff("staff-1", "Name2", "agent", "pw")


class TestAuthenticate:
    async def test_correct(self, db_ready) -> None:
        await staff.create_staff("s1", "Name", "agent", "pw")
        info = await staff.authenticate("s1", "pw")
        assert info is not None
        assert info["staff_id"] == "s1"
        assert info["role"] == "agent"
        assert "password_hash" not in info  # 不暴露 hash

    async def test_wrong_password(self, db_ready) -> None:
        await staff.create_staff("s1", "Name", "agent", "pw")
        assert await staff.authenticate("s1", "WRONG") is None

    async def test_unknown_user(self, db_ready) -> None:
        assert await staff.authenticate("ghost", "pw") is None

    async def test_inactive_rejected(self, db_ready) -> None:
        await staff.create_staff("s1", "Name", "agent", "pw")
        await staff.set_staff_active("s1", 0)
        assert await staff.authenticate("s1", "pw") is None


class TestGetAndListStaff:
    async def test_get_staff(self, db_ready) -> None:
        await staff.create_staff("s1", "Alice", "agent", "pw")
        row = await staff.get_staff("s1")
        assert row is not None
        assert row["display_name"] == "Alice"
        assert row["active"] == 1

    async def test_get_staff_missing(self, db_ready) -> None:
        assert await staff.get_staff("ghost") is None

    async def test_list_staff_ordered_by_id(self, db_ready) -> None:
        await staff.create_staff("zoe", "Zoe", "agent", "pw")
        await staff.create_staff("amy", "Amy", "senior", "pw")
        rows = await staff.list_staff()
        # ORDER BY id：插入顺序
        assert [r["staff_id"] for r in rows] == ["zoe", "amy"]


class TestUpdateStaff:
    async def test_partial_update_display_name(self, db_ready) -> None:
        await staff.create_staff("s1", "Old", "agent", "pw")
        await staff.update_staff("s1", display_name="New")
        row = await staff.get_staff("s1")
        assert row is not None
        assert row["display_name"] == "New"
        assert row["role"] == "agent"  # role 不动

    async def test_partial_update_role(self, db_ready) -> None:
        await staff.create_staff("s1", "Name", "agent", "pw")
        await staff.update_staff("s1", role="senior")
        row = await staff.get_staff("s1")
        assert row is not None and row["role"] == "senior"

    async def test_both_none_keeps_values(self, db_ready) -> None:
        await staff.create_staff("s1", "Name", "agent", "pw")
        await staff.update_staff("s1")  # 都不传
        row = await staff.get_staff("s1")
        assert row is not None
        assert row["display_name"] == "Name"
        assert row["role"] == "agent"

    async def test_invalid_role_raises(self, db_ready) -> None:
        await staff.create_staff("s1", "Name", "agent", "pw")
        with pytest.raises(ValueError):
            await staff.update_staff("s1", role="intern")

    async def test_update_nonexistent_noop(self, db_ready) -> None:
        # UPDATE 0 行不抛错
        await staff.update_staff("ghost", display_name="x")


class TestSetActiveAndResetPassword:
    async def test_set_active_false_then_true(self, db_ready) -> None:
        await staff.create_staff("s1", "Name", "agent", "pw")
        await staff.set_staff_active("s1", 0)
        assert await staff.authenticate("s1", "pw") is None
        await staff.set_staff_active("s1", 1)
        assert await staff.authenticate("s1", "pw") is not None

    async def test_reset_password(self, db_ready) -> None:
        await staff.create_staff("s1", "Name", "agent", "pw")
        await staff.reset_staff_password("s1", "new-pw")
        assert await staff.authenticate("s1", "pw") is None
        assert await staff.authenticate("s1", "new-pw") is not None


