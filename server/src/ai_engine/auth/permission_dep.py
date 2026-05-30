"""动态权限依赖：通过 perm_key 查 role_permissions 矩阵决定放行。

与 require_roles 的关系：require_roles 是按角色集合判定，require_permission 是按权限位判定。
M4 试点用于新端点；旧端点保持 require_roles 不变。
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence import rbac


def require_permission(perm_key: str) -> Callable[..., Any]:
    """生成依赖：检查当前 staff.role 是否拥有 perm_key 权限。"""

    async def _dep(staff: dict[str, Any] = Depends(require_staff)) -> dict[str, Any]:
        role = str(staff.get("role", ""))
        if not await rbac.is_permitted(role, perm_key):
            raise HTTPException(403, f"missing permission: {perm_key}")
        return staff

    return _dep
