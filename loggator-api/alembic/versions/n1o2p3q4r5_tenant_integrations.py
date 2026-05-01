"""Per-tenant integrations (multi OpenSearch / Elastic / Wazuh indexer)

Revision ID: n1o2p3q4r5
Revises: l2m3n4o5p6
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n1o2p3q4r5"
down_revision: Union[str, None] = "l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("extra_config", postgresql.JSONB(), nullable=True),
        sa.Column("opensearch_host", sa.Text(), nullable=True),
        sa.Column("opensearch_port", sa.Integer(), nullable=True),
        sa.Column("opensearch_auth_type", sa.String(20), nullable=True),
        sa.Column("opensearch_username", sa.Text(), nullable=True),
        sa.Column("opensearch_password", sa.Text(), nullable=True),
        sa.Column("opensearch_api_key", sa.Text(), nullable=True),
        sa.Column("opensearch_use_ssl", sa.Boolean(), nullable=True),
        sa.Column("opensearch_verify_certs", sa.Boolean(), nullable=True),
        sa.Column("opensearch_ca_certs", sa.Text(), nullable=True),
        sa.Column("aws_region", sa.String(32), nullable=True),
        sa.Column("opensearch_index_pattern", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tenant_integration_name"),
    )
    op.create_index("ix_tenant_integrations_tenant_id", "tenant_integrations", ["tenant_id"])
    op.create_index(
        "ix_tenant_integrations_one_primary",
        "tenant_integrations",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO tenant_integrations (
                id, tenant_id, name, provider, is_primary, extra_config,
                opensearch_host, opensearch_port, opensearch_auth_type,
                opensearch_username, opensearch_password, opensearch_api_key,
                opensearch_use_ssl, opensearch_verify_certs, opensearch_ca_certs,
                aws_region, opensearch_index_pattern, created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                tenant_id,
                'Default',
                'opensearch',
                true,
                NULL,
                opensearch_host, opensearch_port, opensearch_auth_type,
                opensearch_username, opensearch_password, opensearch_api_key,
                opensearch_use_ssl, opensearch_verify_certs, opensearch_ca_certs,
                aws_region, opensearch_index_pattern,
                NOW(), NOW()
            FROM tenant_connections
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_integrations_one_primary", table_name="tenant_integrations")
    op.drop_index("ix_tenant_integrations_tenant_id", table_name="tenant_integrations")
    op.drop_table("tenant_integrations")
