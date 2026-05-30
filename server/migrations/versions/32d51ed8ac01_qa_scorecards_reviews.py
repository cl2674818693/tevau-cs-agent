"""qa_scorecards_reviews

Revision ID: 32d51ed8ac01
Revises: 9307cc49e1f9
Create Date: 2026-05-30 15:11:42.826370
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '32d51ed8ac01'
down_revision: str | None = '9307cc49e1f9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "qa_scorecards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("items_json", sa.Text(), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_table(
        "qa_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_staff_id", sa.String(64), nullable=False),
        sa.Column("scorecard_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("items_result_json", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(256), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_qa_reviews_conv", "qa_reviews", ["conversation_id"])
    op.create_index(
        "idx_qa_reviews_reviewer", "qa_reviews",
        ["reviewer_staff_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_qa_reviews_reviewer", table_name="qa_reviews")
    op.drop_index("idx_qa_reviews_conv", table_name="qa_reviews")
    op.drop_table("qa_reviews")
    op.drop_table("qa_scorecards")
