"""conversation_client_info

Revision ID: b8d3f9e1a522
Revises: a7c2e8f4d310
Create Date: 2026-06-02 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d3f9e1a522"
down_revision: str | None = "a7c2e8f4d310"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_client_info",
        sa.Column("conversation_id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column("app_version", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("conversation_client_info")
