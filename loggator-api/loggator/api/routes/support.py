"""Human support threads (tenant users and MSP staff)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.api.websocket import broadcast_tenant_event
from loggator.auth.dependencies import require_auth, require_platform_or_msp
from loggator.auth.schemas import UserClaims
from loggator.db.models import SupportMessage, SupportThread, Tenant
from loggator.db.session import get_session
from loggator.tenancy.deps import get_effective_tenant_id
from loggator.tenancy.membership import get_internal_user_id, user_can_access_tenant
from loggator.tenancy.msp_scope import is_msp_admin, is_platform_superadmin

router = APIRouter(prefix="/support", tags=["support"])


class ThreadCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)


class ThreadPatch(BaseModel):
    status: str | None = Field(None, pattern=r"^(open|pending|resolved|closed)$")
    assigned_to_user_id: UUID | None = None


class MessageCreate(BaseModel):
    body: str = Field(..., min_length=1)


class MessageOut(BaseModel):
    id: UUID
    thread_id: UUID
    author_user_id: UUID | None
    body: str
    is_staff: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ThreadOut(BaseModel):
    id: UUID
    tenant_id: UUID
    operator_tenant_id: UUID
    status: str
    subject: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ThreadDetailOut(ThreadOut):
    messages: list[MessageOut]


def _staff_for_thread(user: UserClaims | None, operator_tenant_id: UUID) -> bool:
    if user is None:
        return False
    if is_platform_superadmin(user):
        return True
    return bool(is_msp_admin(user) and user.operator_tenant_id == operator_tenant_id)


@router.post("/threads", response_model=ThreadOut)
async def create_thread(
    body: ThreadCreate,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    if not await user_can_access_tenant(session, user, tenant_id):
        raise HTTPException(status_code=403, detail="Not a member of this tenant")
    t = await session.get(Tenant, tenant_id)
    if t is None or t.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if t.parent_tenant_id is None:
        raise HTTPException(status_code=400, detail="Support is only available for customer tenants")
    uid = await get_internal_user_id(session, user.user_id)
    thread = SupportThread(
        tenant_id=tenant_id,
        operator_tenant_id=t.parent_tenant_id,
        created_by_user_id=uid,
        subject=body.subject.strip(),
    )
    session.add(thread)
    await session.flush()
    if uid:
        session.add(
            SupportMessage(
                thread_id=thread.id,
                author_user_id=uid,
                body=body.subject.strip()[:8000],
                is_staff=False,
            )
        )
    await session.commit()
    await session.refresh(thread)
    await broadcast_tenant_event(
        tenant_id,
        {"type": "support", "action": "thread_created", "thread_id": str(thread.id)},
    )
    return thread


@router.get("/threads", response_model=list[ThreadOut])
async def list_threads_customer(
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
    status: str | None = Query(None, pattern=r"^(open|pending|resolved|closed)$"),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    if is_msp_admin(user) or is_platform_superadmin(user):
        raise HTTPException(
            status_code=400,
            detail="Use GET /platform/support/threads for operator inbox",
        )
    if not await user_can_access_tenant(session, user, tenant_id):
        raise HTTPException(status_code=403, detail="Not a member of this tenant")
    q = select(SupportThread).where(SupportThread.tenant_id == tenant_id)
    if status:
        q = q.where(SupportThread.status == status)
    q = q.order_by(SupportThread.updated_at.desc())
    rows = (await session.execute(q)).scalars().all()
    return list(rows)


@router.get("/threads/{thread_id}", response_model=ThreadDetailOut)
async def get_thread(
    thread_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    thread = await session.get(SupportThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if _staff_for_thread(user, thread.operator_tenant_id):
        pass
    elif thread.tenant_id != tenant_id or not await user_can_access_tenant(session, user, tenant_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    msgs = (
        (
            await session.execute(
                select(SupportMessage)
                .where(SupportMessage.thread_id == thread_id)
                .order_by(SupportMessage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    base = ThreadOut.model_validate(thread)
    return ThreadDetailOut(
        **base.model_dump(),
        messages=[MessageOut.model_validate(m) for m in msgs],
    )


@router.post("/threads/{thread_id}/messages", response_model=MessageOut)
async def post_message(
    thread_id: UUID,
    body: MessageCreate,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_auth),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    thread = await session.get(SupportThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if _staff_for_thread(user, thread.operator_tenant_id):
        raise HTTPException(
            status_code=400,
            detail="Staff must POST to /platform/support/threads/{thread_id}/messages",
        )
    if thread.tenant_id != tenant_id or not await user_can_access_tenant(session, user, tenant_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    uid = await get_internal_user_id(session, user.user_id)
    msg = SupportMessage(
        thread_id=thread_id,
        author_user_id=uid,
        body=body.body.strip()[:8000],
        is_staff=False,
    )
    session.add(msg)
    thread.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(msg)
    await broadcast_tenant_event(
        thread.tenant_id,
        {
            "type": "support",
            "action": "message",
            "thread_id": str(thread_id),
            "is_staff": False,
        },
    )
    return msg


# --- Operator inbox (mounted at /api/v1/platform/support) ---

platform_router = APIRouter(prefix="/platform/support", tags=["support"])


@platform_router.get("/threads", response_model=list[ThreadOut])
async def list_threads_operator(
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
    status: str | None = Query(None, pattern=r"^(open|pending|resolved|closed)$"),
    tenant_id: UUID | None = Query(None),
):
    q = select(SupportThread)
    if is_platform_superadmin(user):
        if tenant_id is not None:
            q = q.where(SupportThread.tenant_id == tenant_id)
    else:
        if user.operator_tenant_id is None:
            return []
        q = q.where(SupportThread.operator_tenant_id == user.operator_tenant_id)
        if tenant_id is not None:
            q = q.where(SupportThread.tenant_id == tenant_id)
    if status:
        q = q.where(SupportThread.status == status)
    q = q.order_by(SupportThread.updated_at.desc())
    rows = (await session.execute(q)).scalars().all()
    return list(rows)


@platform_router.get("/threads/{thread_id}", response_model=ThreadDetailOut)
async def get_thread_operator(
    thread_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    thread = await session.get(SupportThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if not is_platform_superadmin(user):
        if user.operator_tenant_id is None or thread.operator_tenant_id != user.operator_tenant_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    msgs = (
        (
            await session.execute(
                select(SupportMessage)
                .where(SupportMessage.thread_id == thread_id)
                .order_by(SupportMessage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    base = ThreadOut.model_validate(thread)
    return ThreadDetailOut(
        **base.model_dump(),
        messages=[MessageOut.model_validate(m) for m in msgs],
    )


@platform_router.post("/threads/{thread_id}/messages", response_model=MessageOut)
async def post_message_operator(
    thread_id: UUID,
    body: MessageCreate,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    thread = await session.get(SupportThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if not _staff_for_thread(user, thread.operator_tenant_id):
        raise HTTPException(status_code=403, detail="Staff only")
    uid = await get_internal_user_id(session, user.user_id)
    msg = SupportMessage(
        thread_id=thread_id,
        author_user_id=uid,
        body=body.body.strip()[:8000],
        is_staff=True,
    )
    session.add(msg)
    thread.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(msg)
    await broadcast_tenant_event(
        thread.tenant_id,
        {"type": "support", "action": "message", "thread_id": str(thread_id), "is_staff": True},
    )
    return msg


@platform_router.patch("/threads/{thread_id}", response_model=ThreadOut)
async def patch_thread_operator(
    thread_id: UUID,
    body: ThreadPatch,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    thread = await session.get(SupportThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if not _staff_for_thread(user, thread.operator_tenant_id):
        raise HTTPException(status_code=403, detail="Staff only")
    data = body.model_dump(exclude_unset=True)
    if "status" in data:
        thread.status = data["status"]
    if "assigned_to_user_id" in data:
        thread.assigned_to_user_id = data["assigned_to_user_id"]
    thread.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(thread)
    return thread
