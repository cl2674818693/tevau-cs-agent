"""staff_groups_and_skills

Revision ID: 0d69226e9dda
Revises: f68bb295af9d
Create Date: 2026-05-30 16:19:24.930638
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0d69226e9dda'
down_revision: str | None = 'f68bb295af9d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("ux_staff_group_name", "staff_groups", ["name"], unique=True)
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("skills", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.drop_column("skills")
        batch_op.drop_column("group_id")
    op.drop_index("ux_staff_group_name", table_name="staff_groups")
    op.drop_table("staff_groups")
