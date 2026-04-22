"""add_scheduled_analyses

Revision ID: c9d1e2f3a4b5
Revises: b32bfd4fba3b
Create Date: 2026-04-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c9d1e2f3a4b5'
down_revision: Union[str, Sequence[str], None] = 'b32bfd4fba3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scheduled_analyses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('index_pattern', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('affected_services', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('root_causes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('timeline', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('recommendations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('error_count', sa.Integer(), nullable=False),
        sa.Column('warning_count', sa.Integer(), nullable=False),
        sa.Column('log_count', sa.Integer(), nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False),
        sa.Column('model_used', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scheduled_analyses_window_start', 'scheduled_analyses', ['window_start'])
    op.create_index('ix_scheduled_analyses_created_at', 'scheduled_analyses', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_scheduled_analyses_created_at', table_name='scheduled_analyses')
    op.drop_index('ix_scheduled_analyses_window_start', table_name='scheduled_analyses')
    op.drop_table('scheduled_analyses')
