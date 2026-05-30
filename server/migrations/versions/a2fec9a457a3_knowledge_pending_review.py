"""knowledge_pending_review

Revision ID: a2fec9a457a3
Revises: 7dd971914be3
Create Date: 2026-05-30 17:43:04.923021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a2fec9a457a3'
down_revision: str | None = '7dd971914be3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # M4: 扩展 knowledge_entries.status CHECK 加 pending_review 中间态。
    with op.batch_alter_table("knowledge_entries", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "ck_knowledge_status",
            "status IN ('draft','pending_review','published')",
        )


def downgrade() -> None:
    with op.batch_alter_table("knowledge_entries", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "ck_knowledge_status",
            "status IN ('draft','published')",
        )
