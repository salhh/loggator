"""multi_tenant_foundation: tenants, memberships, tenant_connections, tenant_id columns

Revision ID: f3e4d5c6b7a8
Revises: e1f2a3b4c5d6
Create Date: 2026-05-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
revision: str = "f3e4d5c6b7a8"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BOOTSTRAP = "a0000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_subject"), "users", ["subject"], unique=True)

    op.create_table(
        "memberships",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
    )
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False)
    op.create_index(op.f("ix_memberships_tenant_id"), "memberships", ["tenant_id"], unique=False)

    op.create_table(
        "tenant_connections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("opensearch_host", sa.Text(), nullable=True),
        sa.Column("opensearch_port", sa.Integer(), nullable=True),
        sa.Column("opensearch_auth_type", sa.String(length=20), nullable=True),
        sa.Column("opensearch_username", sa.Text(), nullable=True),
        sa.Column("opensearch_password", sa.Text(), nullable=True),
        sa.Column("opensearch_api_key", sa.Text(), nullable=True),
        sa.Column("opensearch_use_ssl", sa.Boolean(), nullable=True),
        sa.Column("opensearch_verify_certs", sa.Boolean(), nullable=True),
        sa.Column("opensearch_ca_certs", sa.Text(), nullable=True),
        sa.Column("aws_region", sa.String(length=32), nullable=True),
        sa.Column("opensearch_index_pattern", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )

    op.execute(
        f"INSERT INTO tenants (id, name, slug, status) VALUES "
        f"('{BOOTSTRAP}', 'Default', 'default', 'active')"
    )

    op.alter_column("app_settings", "key", type_=sa.String(length=255), existing_type=sa.String(length=100))

    op.add_column("summaries", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.add_column("anomalies", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.add_column("alerts", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.add_column("log_embeddings", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.add_column("checkpoints", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.add_column("scheduled_analyses", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.add_column("system_events", sa.Column("tenant_id", sa.UUID(), nullable=True))
    op.add_column("audit_log", sa.Column("tenant_id", sa.UUID(), nullable=True))

    op.execute(sa.text(f"UPDATE summaries SET tenant_id = '{BOOTSTRAP}'"))
    op.execute(sa.text(f"UPDATE anomalies SET tenant_id = '{BOOTSTRAP}'"))
    op.execute(sa.text(f"UPDATE log_embeddings SET tenant_id = '{BOOTSTRAP}'"))
    op.execute(sa.text(f"UPDATE checkpoints SET tenant_id = '{BOOTSTRAP}'"))
    op.execute(sa.text(f"UPDATE scheduled_analyses SET tenant_id = '{BOOTSTRAP}'"))

    op.execute(
        sa.text(
            "UPDATE alerts SET tenant_id = anomalies.tenant_id FROM anomalies "
            "WHERE alerts.anomaly_id = anomalies.id"
        )
    )

    op.alter_column("summaries", "tenant_id", nullable=False)
    op.alter_column("anomalies", "tenant_id", nullable=False)
    op.alter_column("alerts", "tenant_id", nullable=False)
    op.alter_column("log_embeddings", "tenant_id", nullable=False)
    op.alter_column("checkpoints", "tenant_id", nullable=False)
    op.alter_column("scheduled_analyses", "tenant_id", nullable=False)

    op.create_foreign_key("fk_summaries_tenant", "summaries", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_anomalies_tenant", "anomalies", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_alerts_tenant", "alerts", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_log_embeddings_tenant", "log_embeddings", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_checkpoints_tenant", "checkpoints", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_scheduled_analyses_tenant", "scheduled_analyses", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_system_events_tenant", "system_events", "tenants", ["tenant_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_audit_log_tenant", "audit_log", "tenants", ["tenant_id"], ["id"], ondelete="SET NULL")

    op.create_index(op.f("ix_summaries_tenant_id"), "summaries", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_anomalies_tenant_id"), "anomalies", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_alerts_tenant_id"), "alerts", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_log_embeddings_tenant_id"), "log_embeddings", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_checkpoints_tenant_id"), "checkpoints", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_scheduled_analyses_tenant_id"), "scheduled_analyses", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_system_events_tenant_id"), "system_events", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_audit_log_tenant_id"), "audit_log", ["tenant_id"], unique=False)

    op.drop_constraint("checkpoints_index_pattern_key", "checkpoints", type_="unique")
    op.create_unique_constraint("uq_checkpoint_tenant_index", "checkpoints", ["tenant_id", "index_pattern"])

    op.execute(
        f"UPDATE app_settings SET key = 't:{BOOTSTRAP}:' || key "
        f"WHERE key LIKE 'llm:%' OR key LIKE 'alert_channel:%'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE app_settings SET key = regexp_replace(key, "
        f"'^t:{BOOTSTRAP}:', '') "
        f"WHERE key LIKE 't:{BOOTSTRAP}:%'"
    )
    # Simplified downgrade: drop tenant columns and tables — data loss acceptable for dev
    op.drop_constraint("uq_checkpoint_tenant_index", "checkpoints", type_="unique")
    op.create_unique_constraint("checkpoints_index_pattern_key", "checkpoints", ["index_pattern"])

    for t in (
        "audit_log",
        "system_events",
        "scheduled_analyses",
        "checkpoints",
        "log_embeddings",
        "alerts",
        "anomalies",
        "summaries",
    ):
        op.drop_constraint(f"fk_{t}_tenant", t, type_="foreignkey")
        op.drop_index(op.f(f"ix_{t}_tenant_id"), table_name=t)
        op.drop_column(t, "tenant_id")

    op.drop_table("tenant_connections")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("tenants")

    op.alter_column("app_settings", "key", type_=sa.String(length=100), existing_type=sa.String(length=255))
