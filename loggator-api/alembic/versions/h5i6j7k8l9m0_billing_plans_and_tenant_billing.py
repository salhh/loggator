"""Add billing_plans and tenant_billing tables

Revision ID: h5i6j7k8l9m0
Revises: g4h5i6j7k8l9
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h5i6j7k8l9m0"
down_revision: Union[str, None] = "g4h5i6j7k8l9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("max_members", sa.Integer(), nullable=True),
        sa.Column("max_api_calls_per_day", sa.Integer(), nullable=True),
        sa.Column("max_log_volume_mb_per_day", sa.Integer(), nullable=True),
        sa.Column("price_usd_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "tenant_billing",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=True),
        sa.Column("api_calls_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("log_volume_mb_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("billing_cycle_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["billing_plans.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )

    # Seed default plans
    op.execute(
        """
        INSERT INTO billing_plans (id, name, slug, max_members, max_api_calls_per_day, max_log_volume_mb_per_day, price_usd_cents, is_active)
        VALUES
          (gen_random_uuid(), 'Free',       'free',       5,    1000,  500,  0,    true),
          (gen_random_uuid(), 'Pro',        'pro',        25,   10000, 5000, 2900, true),
          (gen_random_uuid(), 'Enterprise', 'enterprise', NULL, NULL,  NULL, 0,    true)
        """
    )


def downgrade() -> None:
    op.drop_table("tenant_billing")
    op.drop_table("billing_plans")
