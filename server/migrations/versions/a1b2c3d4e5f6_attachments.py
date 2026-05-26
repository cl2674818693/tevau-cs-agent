"""attachments: 图片附件元数据表

Revision ID: a1b2c3d4e5f6
Revises: 999833d7e011
Create Date: 2026-05-26 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '999833d7e011'
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
