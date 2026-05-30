"""token_usage_by_model_table

Revision ID: 3ebac6824e12
Revises: 7c471cdd8d62
Create Date: 2026-05-30 17:08:41.032667
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '3ebac6824e12'
down_revision: str | None = '7c471cdd8d62'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_token_usage_by_model",
        sa.Column("subject_id", sa.String(128), primary_key=True),
        sa.Column("user_type", sa.String(8), primary_key=True),
        sa.Column("date", sa.String(16), primary_key=True),
        sa.Column("model", sa.String(32), primary_key=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "INSERT INTO daily_token_usage_by_model"
        "(subject_id, user_type, date, model, input_tokens, output_tokens) "
        "SELECT subject_id, user_type, date, "
        "COALESCE(model, '(unknown)') AS model, "
        "input_tokens, output_tokens "
        "FROM daily_token_usage"
    )


def downgrade() -> None:
    op.drop_table("daily_token_usage_by_model")
