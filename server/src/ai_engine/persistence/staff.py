import hashlib
import secrets
from typing import Any

from ai_engine.persistence.db import get_conn

_VALID_ROLES = {"agent", "senior", "engineer", "admin"}


def hash_password(plain: str, salt: str | None = None) -> str:
    """sha256 + salt；生产建议 argon2，MVP-2 用这个够。"""
    salt = salt or secrets.token_hex(8)
    h = hashlib.sha256((salt + plain).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, _ = hashed.split("$", 1)
    except ValueError:
        return False
    return hash_password(plain, salt) == hashed


async def create_staff(staff_id: str, display_name: str, role: str, password: str) -> int:
    if role not in _VALID_ROLES:
        raise ValueError("invalid role")
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO staff(staff_id, display_name, role, password_hash) VALUES (?,?,?,?)",
            (staff_id, display_name, role, hash_password(password)),
        )
        await conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid


async def authenticate(staff_id: str, password: str) -> dict[str, Any] | None:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT staff_id, display_name, role, password_hash, active "
                "FROM staff WHERE staff_id=?",
                (staff_id,),
            )
        ).fetchone()
    if not row or int(row["active"]) != 1:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return {
        "staff_id": row["staff_id"],
        "display_name": row["display_name"],
        "role": row["role"],
    }


async def get_staff(staff_id: str) -> dict[str, Any] | None:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT staff_id, display_name, role, active FROM staff WHERE staff_id=?",
                (staff_id,),
            )
        ).fetchone()
    return dict(row) if row else None
