"""staff_presence

Revision ID: dd92726e5ff1
Revises: 0d69226e9dda
Create Date: 2026-05-30 16:28:57.473539
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'dd92726e5ff1'
down_revision: str | None = '0d69226e9dda'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_presence",
        sa.Column("staff_id", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="offline"),
        sa.Column("last_seen_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("staff_presence")
