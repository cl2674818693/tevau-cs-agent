import hashlib
import hmac
import secrets
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

_VALID_ROLES = {"agent", "senior", "engineer", "admin", "supervisor", "manager"}
_PBKDF2_ITERATIONS = 600_000


def hash_password(plain: str, salt: str | None = None) -> str:
    """PBKDF2-HMAC-SHA256 慢哈希（stdlib，无新依赖），抗离线爆破。格式 pbkdf2$iter$salt$hex。"""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    parts = hashed.split("$")
    if len(parts) == 4 and parts[0] == "pbkdf2":
        _, iters, salt, h = parts
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), h)
    if len(parts) == 2:  # 兼容历史 sha256 格式 salt$hash（旧库记录登录后可平滑升级）
        salt, h = parts
        return hmac.compare_digest(hashlib.sha256((salt + plain).encode()).hexdigest(), h)
    return False


async def create_staff(staff_id: str, display_name: str, role: str, password: str) -> int:
    if role not in _VALID_ROLES:
        raise ValueError("invalid role")
    return await db.insert_returning_id(
        "INSERT INTO staff(staff_id, display_name, role, password_hash, created_at) "
        "VALUES (:sid, :name, :role, :pw, :now) RETURNING id",
        {
            "sid": staff_id,
            "name": display_name,
            "role": role,
            "pw": hash_password(password),
            "now": now_str(),
        },
    )


async def authenticate(staff_id: str, password: str) -> dict[str, Any] | None:
    row = await db.fetch_one(
        "SELECT staff_id, display_name, role, password_hash, active FROM staff WHERE staff_id=:sid",
        {"sid": staff_id},
    )
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
    return await db.fetch_one(
        "SELECT staff_id, display_name, role, active FROM staff WHERE staff_id=:sid",
        {"sid": staff_id},
    )
