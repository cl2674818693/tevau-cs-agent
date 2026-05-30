"""prompt_drafts

Revision ID: fab2e3750739
Revises: c9876fad654e
Create Date: 2026-05-30 16:49:44.488134
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'fab2e3750739'
down_revision: str | None = 'c9876fad654e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("file_name", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("editor", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_prompt_draft_status"),
    )
    op.create_index(
        "idx_prompt_drafts_lookup", "prompt_drafts",
        ["version", "file_name", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_prompt_drafts_lookup", table_name="prompt_drafts")
    op.drop_table("prompt_drafts")
