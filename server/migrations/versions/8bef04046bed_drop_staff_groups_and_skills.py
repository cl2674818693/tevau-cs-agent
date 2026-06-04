"""drop staff_groups and skills

业务侧 0 消费：分组 / 技能字段除了 admin 后台 CRUD 自己读写，路由 / 分派 / 排班 /
接管 / SLA 都不读。为避免管理员误以为「建组即生效」，连同后台 UI 一起删除。
本迁移清掉表 + 两列。若后续重新做按组路由，再写新 migration 加回
（参考已删除的 0d69226e9dda）。

Revision ID: 8bef04046bed
Revises: b8d3f9e1a522
Create Date: 2026-06-04 16:01:30.471116
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '8bef04046bed'
down_revision: str | None = 'b8d3f9e1a522'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.drop_column("skills")
        batch_op.drop_column("group_id")
    op.drop_index("ux_staff_group_name", table_name="staff_groups")
    op.drop_table("staff_groups")


def downgrade() -> None:
    op.create_table(
        "staff_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("ux_staff_group_name", "staff_groups", ["name"], unique=True)
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("skills", sa.Text(), nullable=True))
