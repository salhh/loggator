"""tenant_api_keys for scoped ingest authentication

Revision ID: g4h5i6j7k8l9
Revises: f3e4d5c6b7a8
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "g4h5i6j7k8l9"
down_revision: Union[str, None] = "f3e4d5c6b7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_api_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenant_api_keys_tenant_id"), "tenant_api_keys", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_tenant_api_keys_key_hash"), "tenant_api_keys", ["key_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenant_api_keys_key_hash"), table_name="tenant_api_keys")
    op.drop_index(op.f("ix_tenant_api_keys_tenant_id"), table_name="tenant_api_keys")
    op.drop_table("tenant_api_keys")
