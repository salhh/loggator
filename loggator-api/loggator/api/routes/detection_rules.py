"""Detection rules — deterministic rule engine for log anomaly detection."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.db.models import DetectionRule
from loggator.db.session import get_session
from loggator.tenancy.authz import assert_tenant_admin_or_platform
from loggator.tenancy.deps import get_effective_tenant_id

router = APIRouter(prefix="/detection-rules", tags=["detection-rules"])

VALID_SEVERITIES = {"low", "medium", "high", "critical"}


class DetectionRuleOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    condition: dict
    severity: str
    mitre_tactics: list
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DetectionRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = None
    condition: dict[str, Any] = Field(
        ...,
        description=(
            "Rule condition DSL. Examples:\n"
            '  field_match: {"type": "field_match", "field": "level", "op": "eq", "value": "ERROR"}\n'
            '  regex: {"type": "regex", "field": "message", "pattern": "(?i)failed login"}\n'
            '  threshold: {"type": "threshold", "field": "level", "value": "ERROR", "count": 10, "window_seconds": 300}'
        ),
    )
    severity: str = Field(default="medium")
    mitre_tactics: list[str] = Field(default_factory=list)
    enabled: bool = Field(default=True)


class DetectionRulePatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[dict[str, Any]] = None
    severity: Optional[str] = None
    mitre_tactics: Optional[list[str]] = None
    enabled: Optional[bool] = None


def _validate_condition(condition: dict) -> None:
    rule_type = condition.get("type")
    if rule_type not in ("field_match", "regex", "threshold"):
        raise HTTPException(
            status_code=400,
            detail="condition.type must be 'field_match', 'regex', or 'threshold'",
        )
    if rule_type in ("field_match", "regex", "threshold"):
        if not condition.get("field"):
            raise HTTPException(status_code=400, detail="condition.field is required")
    if rule_type == "field_match":
        if not condition.get("op") or condition.get("value") is None:
            raise HTTPException(status_code=400, detail="field_match requires 'op' and 'value'")
        if condition["op"] not in ("eq", "neq", "contains", "startswith", "endswith"):
            raise HTTPException(status_code=400, detail="op must be eq|neq|contains|startswith|endswith")
    if rule_type == "regex":
        if not condition.get("pattern"):
            raise HTTPException(status_code=400, detail="regex requires 'pattern'")
    if rule_type == "threshold":
        if not condition.get("count") or not condition.get("window_seconds"):
            raise HTTPException(status_code=400, detail="threshold requires 'count' and 'window_seconds'")


@router.post("", response_model=DetectionRuleOut, status_code=201)
async def create_detection_rule(
    body: DetectionRuleCreate,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    if body.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"severity must be one of {VALID_SEVERITIES}")
    _validate_condition(body.condition)

    row = DetectionRule(
        tenant_id=tenant_id,
        name=body.name.strip(),
        description=body.description,
        condition=body.condition,
        severity=body.severity,
        mitre_tactics=body.mitre_tactics,
        enabled=body.enabled,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.get("", response_model=list[DetectionRuleOut])
async def list_detection_rules(
    enabled: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    q = select(DetectionRule).where(DetectionRule.tenant_id == tenant_id)
    if enabled is not None:
        q = q.where(DetectionRule.enabled == enabled)
    q = q.order_by(DetectionRule.created_at.desc()).limit(limit)
    r = await session.execute(q)
    return list(r.scalars().all())


@router.get("/{id}", response_model=DetectionRuleOut)
async def get_detection_rule(
    id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    r = await session.execute(
        select(DetectionRule).where(DetectionRule.id == id, DetectionRule.tenant_id == tenant_id).limit(1)
    )
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Detection rule not found")
    return row


@router.patch("/{id}", response_model=DetectionRuleOut)
async def patch_detection_rule(
    id: UUID,
    body: DetectionRulePatch,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    r = await session.execute(
        select(DetectionRule).where(DetectionRule.id == id, DetectionRule.tenant_id == tenant_id).limit(1)
    )
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Detection rule not found")

    if body.name is not None:
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description
    if body.condition is not None:
        _validate_condition(body.condition)
        row.condition = body.condition
    if body.severity is not None:
        if body.severity not in VALID_SEVERITIES:
            raise HTTPException(status_code=400, detail=f"severity must be one of {VALID_SEVERITIES}")
        row.severity = body.severity
    if body.mitre_tactics is not None:
        row.mitre_tactics = body.mitre_tactics
    if body.enabled is not None:
        row.enabled = body.enabled

    await session.commit()
    await session.refresh(row)
    return row


@router.delete("/{id}", status_code=204)
async def delete_detection_rule(
    id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    r = await session.execute(
        select(DetectionRule).where(DetectionRule.id == id, DetectionRule.tenant_id == tenant_id).limit(1)
    )
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Detection rule not found")
    await session.delete(row)
    await session.commit()
