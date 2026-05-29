"""admin_audit_log

Revision ID: 5bf2ad794e3e
Revises: 0b3cf2e20201
Create Date: 2026-05-29 18:35:33.416338
"""

import sqlalchemy as sa
from alembic import op

revision: str = '5bf2ad794e3e'
down_revision: str | None = '0b3cf2e20201'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(128), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_admin_audit_created", "admin_audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_admin_audit_created", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
