"""token_usage_model_and_pricing

Revision ID: f68bb295af9d
Revises: 96455014e3e2
Create Date: 2026-05-30 15:33:46.388285
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f68bb295af9d'
down_revision: str | None = '96455014e3e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("daily_token_usage", sa.Column("model", sa.String(32), nullable=True))
    op.create_table(
        "model_pricing",
        sa.Column("model", sa.String(64), primary_key=True),
        sa.Column("input_price_per_1k_x10000", sa.Integer(), nullable=False),
        sa.Column("output_price_per_1k_x10000", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("model_pricing")
    with op.batch_alter_table("daily_token_usage", recreate="always") as batch_op:
        batch_op.drop_column("model")
