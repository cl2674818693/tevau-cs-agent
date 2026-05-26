"""prompt_changes: 灰度变更审计留痕表（Task 6.1）

Revision ID: c3e6a9d2b517
Revises: b2d5f8c1a4e0
Create Date: 2026-05-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3e6a9d2b517'
down_revision: str | None = 'b2d5f8c1a4e0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'prompt_changes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('actor', sa.String(128), nullable=False),
        sa.Column('old_json', sa.Text(), nullable=False),
        sa.Column('new_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('prompt_changes')
