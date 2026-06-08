"""messages: 删 prompt_version 列（灰度版本化已下线 2026-06）

Revision ID: e1f7a3c8b920
Revises: 8bef04046bed
Create Date: 2026-06-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e1f7a3c8b920'
down_revision: str | None = '8bef04046bed'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('messages', 'prompt_version')


def downgrade() -> None:
    op.add_column('messages', sa.Column('prompt_version', sa.String(length=16), nullable=True))
