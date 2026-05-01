"""Deterministic rule engine: evaluate DetectionRules against a log batch.

Each rule condition is a JSON DSL with one of three types:

  field_match  – exact/contains/prefix/suffix match on a log field
  regex        – compiled regex match on a log field
  threshold    – count-based: fires if matching entries exceed `count` in the batch
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import Anomaly, DetectionRule

log = structlog.get_logger()


def _get_field(doc: dict[str, Any], field: str) -> str:
    """Return field value as string (supports dot-notation e.g. 'fields.src_ip')."""
    parts = field.split(".")
    val = doc
    for p in parts:
        if not isinstance(val, dict):
            return ""
        val = val.get(p, "")
    return str(val) if val is not None else ""


def _matches(doc: dict[str, Any], condition: dict[str, Any]) -> bool:
    rule_type = condition.get("type")
    field_val = _get_field(doc, condition.get("field", ""))

    if rule_type == "field_match":
        target = str(condition.get("value", ""))
        op = condition.get("op", "eq")
        if op == "eq":
            return field_val == target
        if op == "neq":
            return field_val != target
        if op == "contains":
            return target.lower() in field_val.lower()
        if op == "startswith":
            return field_val.lower().startswith(target.lower())
        if op == "endswith":
            return field_val.lower().endswith(target.lower())
        return False

    if rule_type == "regex":
        try:
            return bool(re.search(condition.get("pattern", ""), field_val, re.IGNORECASE))
        except re.error:
            return False

    # threshold is handled separately — counted across the whole batch
    return False


async def evaluate_rules(
    session: AsyncSession,
    tenant_id: UUID,
    log_batch: list[dict[str, Any]],
    model_used: str,
    index_pattern: str,
) -> list[Anomaly]:
    """Evaluate all enabled detection rules against `log_batch`.

    Returns a list of Anomaly ORM objects (not yet persisted) for each rule that fired.
    The caller is responsible for saving them and triggering alerts.
    """
    if not log_batch:
        return []

    r = await session.execute(
        select(DetectionRule)
        .where(DetectionRule.tenant_id == tenant_id, DetectionRule.enabled.is_(True))
    )
    rules: list[DetectionRule] = list(r.scalars().all())
    if not rules:
        return []

    fired: list[Anomaly] = []

    for rule in rules:
        condition = rule.condition
        rule_type = condition.get("type")

        if rule_type == "threshold":
            field = condition.get("field", "")
            target = str(condition.get("value", ""))
            op = condition.get("op", "eq")
            required_count = int(condition.get("count", 1))
            matching_docs = [d for d in log_batch if _matches(d, {**condition, "type": "field_match"})]
            if len(matching_docs) < required_count:
                continue
            hit_docs = matching_docs[:10]
        else:
            hit_docs = [d for d in log_batch if _matches(d, condition)]
            if not hit_docs:
                continue

        log.info(
            "rule_engine.rule_fired",
            rule_id=str(rule.id),
            rule_name=rule.name,
            hits=len(hit_docs),
            tenant_id=str(tenant_id),
        )

        anomaly = Anomaly(
            tenant_id=tenant_id,
            index_pattern=index_pattern,
            severity=rule.severity,
            summary=f"[Rule] {rule.name}: {len(hit_docs)} matching log(s) detected",
            root_cause_hints=[rule.description or f"Matched condition: {condition}"],
            mitre_tactics=rule.mitre_tactics or [],
            raw_logs=hit_docs[:20],
            model_used=f"rule:{rule.id}",
            source="rule",
        )
        fired.append(anomaly)

    return fired
