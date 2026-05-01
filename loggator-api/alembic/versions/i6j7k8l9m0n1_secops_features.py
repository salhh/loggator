"""Add SecOps features: anomaly triage, api key expiry, incidents, detection rules, threat indicators

Revision ID: i6j7k8l9m0n1
Revises: h5i6j7k8l9m0
Create Date: 2026-05-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i6j7k8l9m0n1"
down_revision: Union[str, None] = "h5i6j7k8l9m0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── anomalies: triage fields + source + enrichment ─────────────────────
    op.add_column("anomalies", sa.Column("source", sa.String(20), nullable=False, server_default="llm"))
    op.add_column("anomalies", sa.Column("triage_status", sa.String(20), nullable=False, server_default="new"))
    op.add_column("anomalies", sa.Column("triage_note", sa.Text, nullable=True))
    op.add_column("anomalies", sa.Column("triaged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("anomalies", sa.Column("enrichment_context", postgresql.JSONB, nullable=True))

    # ── tenant_api_keys: expiry ─────────────────────────────────────────────
    op.add_column("tenant_api_keys", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))

    # ── incidents ───────────────────────────────────────────────────────────
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("severity", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("linked_anomaly_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("mitre_tactics", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── incident_comments ───────────────────────────────────────────────────
    op.create_table(
        "incident_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_label", sa.Text, nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── detection_rules ─────────────────────────────────────────────────────
    op.create_table(
        "detection_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("condition", postgresql.JSONB, nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("mitre_tactics", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── threat_indicators ───────────────────────────────────────────────────
    op.create_table(
        "threat_indicators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ioc_type", sa.String(20), nullable=False),
        sa.Column("value", sa.Text, nullable=False, index=True),
        sa.Column("reputation", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("confidence_score", sa.Integer, nullable=True),
        sa.Column("source", sa.Text, nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ioc_type", "value", name="uq_threat_indicator_type_value"),
    )


def downgrade() -> None:
    op.drop_table("threat_indicators")
    op.drop_table("detection_rules")
    op.drop_table("incident_comments")
    op.drop_table("incidents")
    op.drop_column("tenant_api_keys", "expires_at")
    op.drop_column("anomalies", "enrichment_context")
    op.drop_column("anomalies", "triaged_at")
    op.drop_column("anomalies", "triage_note")
    op.drop_column("anomalies", "triage_status")
    op.drop_column("anomalies", "source")
