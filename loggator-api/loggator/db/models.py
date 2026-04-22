import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    log_timestamp = Column(DateTime(timezone=True), nullable=True)
    index_pattern = Column(Text, nullable=False)
    severity = Column(String(10), nullable=False)  # low | medium | high
    summary = Column(Text, nullable=False)
    root_cause_hints = Column(JSONB, nullable=False, default=list)
    mitre_tactics = Column(JSONB, nullable=False, default=list, server_default="[]")
    raw_logs = Column(JSONB, nullable=True)
    model_used = Column(String(100), nullable=False)
    alerted = Column(Boolean, nullable=False, default=False)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    log_timestamp = Column(DateTime(timezone=True), nullable=True)
    index_pattern = Column(Text, nullable=False)
    text = Column(Text, nullable=False)          # rendered log line sent to embedder
    embedding = Column(Vector(768), nullable=False)  # nomic-embed-text dim
    metadata_ = Column("metadata", JSONB, nullable=True)  # service, host, level, etc.


class AppSettings(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    index_pattern = Column(Text, nullable=False, unique=True)
    last_sort = Column(JSONB, nullable=True)  # search_after cursor value
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
