"""knowledge_entries

Revision ID: 8584b9fdd05a
Revises: fab2e3750739
Create Date: 2026-05-30 16:53:25.259904
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '8584b9fdd05a'
down_revision: str | None = 'fab2e3750739'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False, server_default="zh"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("source_gap_signal", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.CheckConstraint("type IN ('api_doc','error_code','faq')", name="ck_knowledge_type"),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_knowledge_status"),
    )
    op.create_index(
        "ux_knowledge_key", "knowledge_entries",
        ["type", "key", "locale", "status"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_knowledge_key", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")
