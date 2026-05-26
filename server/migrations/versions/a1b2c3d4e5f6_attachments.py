"""attachments: 图片附件元数据表

Revision ID: a1b2c3d4e5f6
Revises: c3e6a9d2b517
Create Date: 2026-05-26 16:30:00.000000

注：本迁移对应表早已提交进 schema.py（聊天图片功能），但迁移文件长期只暂存未提交，
导致 alembic 链缺该表（test_alembic_upgrade_matches_init_db_schema 失败）。此处补提交并
接到本分支迁移链末尾（原 down_revision 999833 与本分支迁移同基点会造成多 head）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = 'c3e6a9d2b517'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('attachments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=True),
    sa.Column('uploader_type', sa.String(length=8), nullable=False),
    sa.Column('uploader_id', sa.String(length=128), nullable=False),
    sa.Column('object_key', sa.Text(), nullable=False),
    sa.Column('mime', sa.String(length=64), nullable=False),
    sa.Column('byte_size', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_att_conv', 'attachments', ['conversation_id'], unique=False)
    op.create_index('idx_att_msg', 'attachments', ['message_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_att_msg', table_name='attachments')
    op.drop_index('idx_att_conv', table_name='attachments')
    op.drop_table('attachments')
