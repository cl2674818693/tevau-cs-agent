"""guardrail_rules

Revision ID: 4db4ec4d9a09
Revises: 8584b9fdd05a
Create Date: 2026-05-30 16:57:42.367494
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '4db4ec4d9a09'
down_revision: str | None = '8584b9fdd05a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guardrail_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("pattern", sa.String(512), nullable=False),
        sa.Column("action", sa.String(16), nullable=False, server_default="block"),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "type IN ('blocklist','sensitive_word','scope_toggle')",
            name="ck_guardrail_type",
        ),
        sa.CheckConstraint("action IN ('block','flag')", name="ck_guardrail_action"),
    )
    op.create_index("idx_guardrail_active", "guardrail_rules", ["active", "type"])


def downgrade() -> None:
    op.drop_index("idx_guardrail_active", table_name="guardrail_rules")
    op.drop_table("guardrail_rules")
