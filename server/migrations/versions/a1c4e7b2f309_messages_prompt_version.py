"""messages: 增 prompt_version 列（灰度 A/B 评估，assistant 行落库）

Revision ID: a1c4e7b2f309
Revises: ff78e275941d
Create Date: 2026-05-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1c4e7b2f309'
down_revision: str | None = 'ff78e275941d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('prompt_version', sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'prompt_version')
