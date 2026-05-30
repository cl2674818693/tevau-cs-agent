"""agent_ratings

Revision ID: d5deba890d73
Revises: 32d51ed8ac01
Create Date: 2026-05-30 15:18:12.105078
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd5deba890d73'
down_revision: str | None = '32d51ed8ac01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_ratings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("user_type", sa.String(8), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_agent_rating_range"),
    )
    op.create_index("idx_agent_ratings_staff", "agent_ratings", ["staff_id", "created_at"])
    op.create_index("idx_agent_ratings_conv", "agent_ratings", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("idx_agent_ratings_conv", table_name="agent_ratings")
    op.drop_index("idx_agent_ratings_staff", table_name="agent_ratings")
    op.drop_table("agent_ratings")
