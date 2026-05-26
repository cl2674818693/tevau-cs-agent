"""conversations: 增 needs_review 列（👎 反馈标记待复核）

Revision ID: b2d5f8c1a4e0
Revises: a1c4e7b2f309
Create Date: 2026-05-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b2d5f8c1a4e0'
down_revision: str | None = 'a1c4e7b2f309'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'conversations',
        sa.Column('needs_review', sa.Integer(), server_default='0', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('conversations', 'needs_review')
