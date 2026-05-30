"""routing_rules_and_target_group

Revision ID: c9876fad654e
Revises: d74b70c64e37
Create Date: 2026-05-30 16:36:27.179612
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c9876fad654e'
down_revision: str | None = 'd74b70c64e37'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "routing_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_type", sa.String(32), nullable=False),
        sa.Column("match_value", sa.String(256), nullable=False),
        sa.Column("target_group_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "match_type IN ('user_type','scope','keyword')",
            name="ck_routing_match_type",
        ),
    )
    op.create_index("idx_routing_priority", "routing_rules", ["priority", "active"])
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("target_group_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_column("target_group_id")
    op.drop_index("idx_routing_priority", table_name="routing_rules")
    op.drop_table("routing_rules")
