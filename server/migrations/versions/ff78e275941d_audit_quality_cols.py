"""audit: tool_audits 增 result_count/is_empty/subject_id/user_type

Revision ID: ff78e275941d
Revises: 999833d7e011
Create Date: 2026-05-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'ff78e275941d'
down_revision: str | None = '999833d7e011'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('tool_audits', sa.Column('result_count', sa.Integer(), nullable=True))
    op.add_column('tool_audits', sa.Column('is_empty', sa.Integer(), nullable=True))
    op.add_column('tool_audits', sa.Column('subject_id', sa.String(length=128), nullable=True))
    op.add_column('tool_audits', sa.Column('user_type', sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column('tool_audits', 'user_type')
    op.drop_column('tool_audits', 'subject_id')
    op.drop_column('tool_audits', 'is_empty')
    op.drop_column('tool_audits', 'result_count')
