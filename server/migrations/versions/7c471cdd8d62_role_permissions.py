"""role_permissions

Revision ID: 7c471cdd8d62
Revises: 4db4ec4d9a09
Create Date: 2026-05-30 17:06:24.472446
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '7c471cdd8d62'
down_revision: str | None = '4db4ec4d9a09'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("permission_key", sa.String(64), nullable=False),
        sa.Column("allowed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index(
        "ux_role_perm", "role_permissions",
        ["role", "permission_key"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_role_perm", table_name="role_permissions")
    op.drop_table("role_permissions")
