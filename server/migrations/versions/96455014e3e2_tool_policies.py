"""tool_policies

Revision ID: 96455014e3e2
Revises: d5deba890d73
Create Date: 2026-05-30 15:26:54.944384
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '96455014e3e2'
down_revision: str | None = 'd5deba890d73'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("allowed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unmask_allowed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index(
        "ux_tool_policy_role", "tool_policies", ["tool_name", "role"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ux_tool_policy_role", table_name="tool_policies")
    op.drop_table("tool_policies")
