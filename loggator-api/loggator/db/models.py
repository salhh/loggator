import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    slug = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="active")  # active | suspended
    parent_tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True, index=True)
    is_operator = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject = Column(String(255), nullable=False, unique=True, index=True)  # OIDC sub
    email = Column(String(255), nullable=False, default="")
    display_name = Column(String(255), nullable=True)
    password_hash = Column(Text, nullable=True)  # bcrypt, local login only
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    role = Column(String(32), nullable=False)  # platform_admin | msp_admin | tenant_admin | tenant_member
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),)


class TenantConnection(Base):
    """Per-tenant OpenSearch (and future) connection; empty row falls back to global Settings."""

    __tablename__ = "tenant_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    opensearch_host = Column(Text, nullable=True)
    opensearch_port = Column(Integer, nullable=True)
    opensearch_auth_type = Column(String(20), nullable=True)  # none | basic | api_key | aws_iam
    opensearch_username = Column(Text, nullable=True)
    opensearch_password = Column(Text, nullable=True)
    opensearch_api_key = Column(Text, nullable=True)
    opensearch_use_ssl = Column(Boolean, nullable=True)
    opensearch_verify_certs = Column(Boolean, nullable=True)
    opensearch_ca_certs = Column(Text, nullable=True)
    aws_region = Column(String(32), nullable=True)
    opensearch_index_pattern = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TenantIntegration(Base):
    """Per-tenant log/SIEM integration (OpenSearch, Elasticsearch, Wazuh indexer, etc.)."""

    __tablename__ = "tenant_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(Text, nullable=False)
    provider = Column(String(32), nullable=False)  # opensearch | elasticsearch | wazuh_indexer | wazuh_api
    is_primary = Column(Boolean, nullable=False, default=False)
    extra_config = Column(JSONB, nullable=True)
    opensearch_host = Column(Text, nullable=True)
    opensearch_port = Column(Integer, nullable=True)
    opensearch_auth_type = Column(String(20), nullable=True)
    opensearch_username = Column(Text, nullable=True)
    opensearch_password = Column(Text, nullable=True)
    opensearch_api_key = Column(Text, nullable=True)
    opensearch_use_ssl = Column(Boolean, nullable=True)
    opensearch_verify_certs = Column(Boolean, nullable=True)
    opensearch_ca_certs = Column(Text, nullable=True)
    aws_region = Column(String(32), nullable=True)
    opensearch_index_pattern = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_tenant_integration_name"),)


class TenantApiKey(Base):
    """Per-tenant API keys (e.g. log ingest). Plaintext is shown only once at creation."""

    __tablename__ = "tenant_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(Text, nullable=False)
    key_prefix = Column(String(24), nullable=False)
    key_hash = Column(String(64), nullable=False, index=True)
    scopes = Column(JSONB, nullable=False, default=list)  # e.g. ["ingest"]
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    index_pattern = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    top_issues = Column(JSONB, nullable=False, default=list)
    error_count = Column(Integer, nullable=False, default=0)
    recommendation = Column(Text, nullable=True)
    model_used = Column(String(100), nullable=False)
    tokens_used = Column(Integer, nullable=True)


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    log_timestamp = Column(DateTime(timezone=True), nullable=True)
    index_pattern = Column(Text, nullable=False)
    severity = Column(String(10), nullable=False)  # low | medium | high
    summary = Column(Text, nullable=False)
    root_cause_hints = Column(JSONB, nullable=False, default=list)
    mitre_tactics = Column(JSONB, nullable=False, default=list, server_default="[]")
    raw_logs = Column(JSONB, nullable=True)
    enrichment_context = Column(JSONB, nullable=True)  # threat intel results
    model_used = Column(String(100), nullable=False)
    alerted = Column(Boolean, nullable=False, default=False)
    source = Column(String(20), nullable=False, default="llm")  # llm | rule | ueba
    triage_status = Column(String(20), nullable=False, default="new")  # new | acknowledged | suppressed | false_positive
    triage_note = Column(Text, nullable=True)
    triaged_at = Column(DateTime(timezone=True), nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    anomaly_id = Column(UUID(as_uuid=True), ForeignKey("anomalies.id"), nullable=False)
    channel = Column(String(20), nullable=False)  # slack | email | webhook
    destination = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)
    status = Column(String(10), nullable=False, default="pending")  # sent | failed | pending
    error = Column(Text, nullable=True)


class LogEmbedding(Base):
    __tablename__ = "log_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    log_timestamp = Column(DateTime(timezone=True), nullable=True)
    index_pattern = Column(Text, nullable=False)
    text = Column(Text, nullable=False)          # rendered log line sent to embedder
    embedding = Column(Vector(768), nullable=False)  # nomic-embed-text dim
    metadata_ = Column("metadata", JSONB, nullable=True)  # service, host, level, etc.


class AppSettings(Base):
    __tablename__ = "app_settings"

    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    index_pattern = Column(Text, nullable=False)
    last_sort = Column(JSONB, nullable=True)  # search_after cursor value
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("tenant_id", "index_pattern", name="uq_checkpoint_tenant_index"),)


class ScheduledAnalysis(Base):
    __tablename__ = "scheduled_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    index_pattern = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    affected_services = Column(JSONB, nullable=False, default=list)
    root_causes = Column(JSONB, nullable=False, default=list)
    timeline = Column(JSONB, nullable=False, default=list)
    recommendations = Column(JSONB, nullable=False, default=list)
    error_count = Column(Integer, nullable=False, default=0)
    warning_count = Column(Integer, nullable=False, default=0)
    log_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    model_used = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="success")  # "success" | "failed"


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    service = Column(Text, nullable=False)   # llm | opensearch | postgres | scheduler | alerts | streaming
    event_type = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)  # info | warning | error | critical
    message = Column(Text, nullable=False)
    details = Column(JSONB, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    request_id = Column(Text, nullable=False)
    method = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=True)  # None if request crashed before response
    duration_ms = Column(Integer, nullable=True)
    client_ip = Column(Text, nullable=True)
    query_params = Column(JSONB, nullable=True)
    error_detail = Column(Text, nullable=True)
    actor_id = Column(Text, nullable=True)
    actor_type = Column(Text, nullable=True)


class BillingPlan(Base):
    __tablename__ = "billing_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    slug = Column(String(64), nullable=False, unique=True)
    max_members = Column(Integer, nullable=True)
    max_api_calls_per_day = Column(Integer, nullable=True)
    max_log_volume_mb_per_day = Column(Integer, nullable=True)
    price_usd_cents = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TenantBilling(Base):
    __tablename__ = "tenant_billing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("billing_plans.id", ondelete="SET NULL"), nullable=True)
    api_calls_today = Column(Integer, nullable=False, default=0)
    log_volume_mb_today = Column(Integer, nullable=False, default=0)
    billing_cycle_start = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Incident(Base):
    """Security incident created from one or more anomalies."""

    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="open")  # open | investigating | resolved | false_positive
    severity = Column(String(10), nullable=False, default="medium")  # low | medium | high | critical
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    linked_anomaly_ids = Column(JSONB, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    mitre_tactics = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class IncidentComment(Base):
    """Threaded comment on an incident for analyst collaboration."""

    __tablename__ = "incident_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_label = Column(Text, nullable=True)  # cached display name / email at write time
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DetectionRule(Base):
    """Deterministic detection rule evaluated against every log batch."""

    __tablename__ = "detection_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    # condition stored as JSON DSL: {"type": "field_match"|"threshold"|"regex", ...}
    condition = Column(JSONB, nullable=False)
    severity = Column(String(10), nullable=False, default="medium")
    mitre_tactics = Column(JSONB, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ThreatIndicator(Base):
    """Cached threat intelligence lookup results (IP reputation, domain, hash)."""

    __tablename__ = "threat_indicators"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ioc_type = Column(String(20), nullable=False)   # ip | domain | hash
    value = Column(Text, nullable=False, index=True)
    reputation = Column(String(20), nullable=False, default="unknown")  # clean | suspicious | malicious | unknown
    confidence_score = Column(Integer, nullable=True)   # 0-100
    source = Column(Text, nullable=True)               # abuseipdb | greynoise | otx
    details = Column(JSONB, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("ioc_type", "value", name="uq_threat_indicator_type_value"),)


class SupportThread(Base):
    __tablename__ = "support_threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    operator_tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default="open")  # open | pending | resolved | closed
    subject = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("support_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body = Column(Text, nullable=False)
    is_staff = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
