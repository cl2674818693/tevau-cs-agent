"""drop_daily_token_usage

Revision ID: 7dd971914be3
Revises: 29c36d1e2bb6
Create Date: 2026-05-30 17:33:34.170537
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '7dd971914be3'
down_revision: str | None = '29c36d1e2bb6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("daily_token_usage")


def downgrade() -> None:
    op.create_table(
        "daily_token_usage",
        sa.Column("subject_id", sa.String(128), primary_key=True),
        sa.Column("user_type", sa.String(8), primary_key=True),
        sa.Column("date", sa.String(16), primary_key=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(32), nullable=True),
    )
