"""admin_console_m1

Revision ID: 0b3cf2e20201
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 18:22:59.581999
"""

from collections.abc import Sequence

from alembic import op

revision: str = '0b3cf2e20201'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # staff: 角色 CHECK 扩展到 6 角色（batch 兼容 SQLite 重建 / PG 直接 ALTER）
    with op.batch_alter_table("staff", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "ck_staff_role",
            "role IN ('agent','senior','engineer','admin','supervisor','manager')",
        )


def downgrade() -> None:
    with op.batch_alter_table("staff", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "ck_staff_role", "role IN ('agent','senior','engineer','admin')"
        )
