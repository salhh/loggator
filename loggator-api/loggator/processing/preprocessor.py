import hashlib
import re
from datetime import datetime, timezone
from typing import Any

import structlog

log = structlog.get_logger()

# Log levels to drop entirely (configurable via blocklist)
_DEFAULT_LEVEL_BLOCKLIST = {"DEBUG", "TRACE"}

# Regex patterns for noise messages to drop (health checks, k8s probes, etc.)
_NOISE_PATTERNS = [
    re.compile(r"health.?check", re.IGNORECASE),
    re.compile(r"readiness.?probe", re.IGNORECASE),
    re.compile(r"liveness.?probe", re.IGNORECASE),
    re.compile(r"GET /health", re.IGNORECASE),
    re.compile(r"GET /ping", re.IGNORECASE),
    re.compile(r"GET /metrics", re.IGNORECASE),
]

# Field name aliases → canonical name
_LEVEL_ALIASES = ["severity", "log.level", "log_level", "LogLevel", "Severity"]
_MESSAGE_ALIASES = ["msg", "log", "body", "text", "log.message"]
_TIMESTAMP_ALIASES = ["timestamp", "time", "ts", "event_time", "created_at"]
_HOST_ALIASES = ["hostname", "host.name", "node", "server"]
_SERVICE_ALIASES = ["app", "application", "service_name", "component"]


def _normalize_field(doc: dict, canonical: str, aliases: list[str]) -> None:
    """Rename the first matching alias to the canonical field name."""
    if canonical in doc:
        return
    for alias in aliases:
        if alias in doc:
            doc[canonical] = doc.pop(alias)
            return


def _normalize_timestamp(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        # Unix epoch seconds or milliseconds
        ts = value / 1000 if value > 1e10 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return None


def _dedup_key(doc: dict) -> str:
    """Hash key for deduplication — based on message template + host + level."""
    message = doc.get("message", "")
    # Strip numbers so "timeout after 30s" and "timeout after 60s" collapse
    template = re.sub(r"\d+", "N", message)
    host = doc.get("host", "")
    level = doc.get("level", "")
    raw = f"{level}|{host}|{template}"
    return hashlib.md5(raw.encode()).hexdigest()


def preprocess(
    docs: list[dict],
    level_blocklist: set[str] | None = None,
    max_message_length: int = 2000,
) -> list[dict]:
    """
    Filter, normalize, and deduplicate a batch of raw OpenSearch documents.
    Returns a cleaned list ready for chunking.
    """
    blocklist = level_blocklist or _DEFAULT_LEVEL_BLOCKLIST
    seen_keys: dict[str, int] = {}  # dedup_key → count
    results: list[dict] = []

    for doc in docs:
        # --- Normalize field names ---
        _normalize_field(doc, "level", _LEVEL_ALIASES)
        _normalize_field(doc, "message", _MESSAGE_ALIASES)
        _normalize_field(doc, "@timestamp", _TIMESTAMP_ALIASES)
        _normalize_field(doc, "host", _HOST_ALIASES)
        _normalize_field(doc, "service", _SERVICE_ALIASES)

        # --- Normalize timestamp ---
        if "@timestamp" in doc:
            doc["@timestamp"] = _normalize_timestamp(doc["@timestamp"]) or doc["@timestamp"]

        # --- Uppercase level ---
        level = str(doc.get("level", "")).upper()
        doc["level"] = level

        # --- Filter: drop blocked levels ---
        if level in blocklist:
            continue

        # --- Filter: drop noise messages ---
        message = str(doc.get("message", ""))
        if any(p.search(message) for p in _NOISE_PATTERNS):
            continue

        # --- Filter: drop docs missing required fields ---
        if not message:
            continue

        # --- Truncate huge messages ---
        if len(message) > max_message_length:
            doc["message"] = message[:max_message_length] + "... [truncated]"

        # --- Deduplicate ---
        key = _dedup_key(doc)
        if key in seen_keys:
            seen_keys[key] += 1
            continue
        seen_keys[key] = 1
        results.append(doc)

    # Annotate collapsed duplicates count back onto surviving docs
    for doc in results:
        key = _dedup_key(doc)
        count = seen_keys.get(key, 1)
        if count > 1:
            doc["_occurrences"] = count

    original = len(docs)
    after = len(results)
    log.info("preprocessor.done", original=original, after=after, dropped=original - after)
    return results
