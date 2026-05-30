"""report_definitions

Revision ID: 29c36d1e2bb6
Revises: 3ebac6824e12
Create Date: 2026-05-30 17:10:23.153769
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '29c36d1e2bb6'
down_revision: str | None = '3ebac6824e12'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("dims_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("filters_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "metrics_json", sa.Text(), nullable=False,
            server_default='[{"op":"count","col":"*","alias":"n"}]',
        ),
        sa.Column("owner", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_reports_owner", "report_definitions", ["owner"])


def downgrade() -> None:
    op.drop_index("idx_reports_owner", table_name="report_definitions")
    op.drop_table("report_definitions")
