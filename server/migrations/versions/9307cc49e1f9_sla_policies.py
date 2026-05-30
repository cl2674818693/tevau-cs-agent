"""sla_policies

Revision ID: 9307cc49e1f9
Revises: 5bf2ad794e3e
Create Date: 2026-05-30 13:35:57.430226
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '9307cc49e1f9'
down_revision: str | None = '5bf2ad794e3e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sla_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("threshold_seconds", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False, server_default="all"),
        sa.Column("scope_value", sa.String(64), nullable=True),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint("metric IN ('take_time','resolve_time')", name="ck_sla_metric"),
    )


def downgrade() -> None:
    op.drop_table("sla_policies")
