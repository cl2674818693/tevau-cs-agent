"""pending_timeout_pushes

Revision ID: a7c2e8f4d310
Revises: e5a3f29d1b07
Create Date: 2026-06-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c2e8f4d310"
down_revision: str | None = "e5a3f29d1b07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_timeout_pushes",
        sa.Column("conversation_id", sa.Integer(), primary_key=True),
        sa.Column("pushed_at", sa.String(32), nullable=False),
        sa.Column("threshold_seconds", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pending_timeout_pushes")
