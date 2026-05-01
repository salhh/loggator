"""Incident management — lifecycle, assignment, and comments."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.db.models import Incident, IncidentComment, User
from loggator.db.session import get_session
from loggator.tenancy.deps import get_effective_tenant_id
from loggator.tenancy.membership import get_internal_user_id

router = APIRouter(prefix="/incidents", tags=["incidents"])

VALID_STATUSES = {"open", "investigating", "resolved", "false_positive"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


class IncidentCommentOut(BaseModel):
    id: UUID
    incident_id: UUID
    author_id: Optional[UUID]
    author_label: Optional[str]
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class IncidentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    status: str
    severity: str
    assignee_id: Optional[UUID]
    linked_anomaly_ids: list
    notes: Optional[str]
    mitre_tactics: list
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    severity: str = Field(default="medium")
    notes: Optional[str] = None
    linked_anomaly_ids: list[str] = Field(default_factory=list)
    mitre_tactics: list[str] = Field(default_factory=list)


class IncidentPatch(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    assignee_subject: Optional[str] = None  # OIDC subject of the assignee
    notes: Optional[str] = None
    linked_anomaly_ids: Optional[list[str]] = None
    mitre_tactics: Optional[list[str]] = None


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1)


@router.post("", response_model=IncidentOut, status_code=201)
async def create_incident(
    body: IncidentCreate,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    if body.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"severity must be one of {VALID_SEVERITIES}")
    row = Incident(
        tenant_id=tenant_id,
        title=body.title.strip(),
        severity=body.severity,
        notes=body.notes,
        linked_anomaly_ids=body.linked_anomaly_ids,
        mitre_tactics=body.mitre_tactics,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.get("", response_model=list[IncidentOut])
async def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    q = select(Incident).where(Incident.tenant_id == tenant_id)
    if status:
        q = q.where(Incident.status == status)
    if severity:
        q = q.where(Incident.severity == severity)
    q = q.order_by(Incident.created_at.desc()).limit(limit).offset(offset)
    r = await session.execute(q)
    return list(r.scalars().all())


@router.get("/{id}", response_model=IncidentOut)
async def get_incident(
    id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    r = await session.execute(
        select(Incident).where(Incident.id == id, Incident.tenant_id == tenant_id).limit(1)
    )
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    return row


@router.patch("/{id}", response_model=IncidentOut)
async def patch_incident(
    id: UUID,
    body: IncidentPatch,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    r = await session.execute(
        select(Incident).where(Incident.id == id, Incident.tenant_id == tenant_id).limit(1)
    )
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")

    if body.title is not None:
        row.title = body.title.strip()
    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"status must be one of {VALID_STATUSES}")
        row.status = body.status
        if body.status == "resolved" and row.resolved_at is None:
            row.resolved_at = datetime.now(timezone.utc)
    if body.severity is not None:
        if body.severity not in VALID_SEVERITIES:
            raise HTTPException(status_code=400, detail=f"severity must be one of {VALID_SEVERITIES}")
        row.severity = body.severity
    if body.notes is not None:
        row.notes = body.notes
    if body.linked_anomaly_ids is not None:
        row.linked_anomaly_ids = body.linked_anomaly_ids
    if body.mitre_tactics is not None:
        row.mitre_tactics = body.mitre_tactics
    if body.assignee_subject is not None:
        uid = await get_internal_user_id(session, body.assignee_subject)
        row.assignee_id = uid

    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    return row


@router.delete("/{id}", status_code=204)
async def delete_incident(
    id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    r = await session.execute(
        select(Incident).where(Incident.id == id, Incident.tenant_id == tenant_id).limit(1)
    )
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Incident not found")
    await session.delete(row)
    await session.commit()


# ── Comments ──────────────────────────────────────────────────────────────────

@router.get("/{id}/comments", response_model=list[IncidentCommentOut])
async def list_comments(
    id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    # Verify incident belongs to tenant
    r = await session.execute(
        select(Incident.id).where(Incident.id == id, Incident.tenant_id == tenant_id).limit(1)
    )
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")
    r2 = await session.execute(
        select(IncidentComment).where(IncidentComment.incident_id == id).order_by(IncidentComment.created_at.asc())
    )
    return list(r2.scalars().all())


@router.post("/{id}/comments", response_model=IncidentCommentOut, status_code=201)
async def add_comment(
    id: UUID,
    body: CommentCreate,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    r = await session.execute(
        select(Incident.id).where(Incident.id == id, Incident.tenant_id == tenant_id).limit(1)
    )
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")

    author_id = None
    author_label = None
    if user:
        uid = await get_internal_user_id(session, user.user_id)
        author_id = uid
        # Cache display label at write time
        if uid:
            ur = await session.execute(select(User).where(User.id == uid).limit(1))
            u = ur.scalar_one_or_none()
            author_label = (u.display_name or u.email or user.email or user.user_id) if u else user.email

    comment = IncidentComment(
        incident_id=id,
        author_id=author_id,
        author_label=author_label,
        body=body.body.strip(),
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return comment
