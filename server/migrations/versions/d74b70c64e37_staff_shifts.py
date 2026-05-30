"""staff_shifts

Revision ID: d74b70c64e37
Revises: dd92726e5ff1
Create Date: 2026-05-30 16:32:55.884985
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd74b70c64e37'
down_revision: str | None = 'dd92726e5ff1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_shifts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("staff_id", sa.String(64), nullable=False),
        sa.Column("start_at", sa.String(32), nullable=False),
        sa.Column("end_at", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_shifts_staff_time", "staff_shifts", ["staff_id", "start_at"])


def downgrade() -> None:
    op.drop_index("idx_shifts_staff_time", table_name="staff_shifts")
    op.drop_table("staff_shifts")
