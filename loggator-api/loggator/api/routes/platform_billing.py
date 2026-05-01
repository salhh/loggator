"""Platform-admin billing plans and per-tenant billing management (MSP-scoped)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_platform_or_msp, require_platform_superadmin
from loggator.auth.schemas import UserClaims
from loggator.db.models import BillingPlan, TenantBilling
from loggator.db.session import get_session
from loggator.tenancy.msp_scope import assert_msp_or_platform_can_touch_tenant

router = APIRouter(prefix="/platform/billing", tags=["platform"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class BillingPlanOut(BaseModel):
    id: UUID
    name: str
    slug: str
    max_members: int | None
    max_api_calls_per_day: int | None
    max_log_volume_mb_per_day: int | None
    price_usd_cents: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BillingPlanCreate(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    max_members: int | None = None
    max_api_calls_per_day: int | None = None
    max_log_volume_mb_per_day: int | None = None
    price_usd_cents: int = 0


class BillingPlanPatch(BaseModel):
    name: str | None = None
    max_members: int | None = None
    max_api_calls_per_day: int | None = None
    max_log_volume_mb_per_day: int | None = None
    price_usd_cents: int | None = None
    is_active: bool | None = None


class TenantBillingOut(BaseModel):
    id: UUID
    tenant_id: UUID
    plan_id: UUID | None
    plan: BillingPlanOut | None
    api_calls_today: int
    log_volume_mb_today: int
    billing_cycle_start: datetime | None
    notes: str | None
    limits_exceeded: bool
    updated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class TenantBillingUpsert(BaseModel):
    plan_id: UUID | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _billing_out(billing: TenantBilling, plan: BillingPlan | None) -> TenantBillingOut:
    exceeded = False
    if plan:
        if plan.max_members is not None and billing.api_calls_today > plan.max_api_calls_per_day:
            exceeded = True
        if plan.max_api_calls_per_day is not None and billing.api_calls_today > plan.max_api_calls_per_day:
            exceeded = True
        if plan.max_log_volume_mb_per_day is not None and billing.log_volume_mb_today > plan.max_log_volume_mb_per_day:
            exceeded = True
    return TenantBillingOut(
        id=billing.id,
        tenant_id=billing.tenant_id,
        plan_id=billing.plan_id,
        plan=BillingPlanOut.model_validate(plan) if plan else None,
        api_calls_today=billing.api_calls_today,
        log_volume_mb_today=billing.log_volume_mb_today,
        billing_cycle_start=billing.billing_cycle_start,
        notes=billing.notes,
        limits_exceeded=exceeded,
        updated_at=billing.updated_at,
        created_at=billing.created_at,
    )


# ---------------------------------------------------------------------------
# Plan routes
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=list[BillingPlanOut])
async def list_plans(
    session: AsyncSession = Depends(get_session),
    _: UserClaims = Depends(require_platform_or_msp),
):
    result = await session.execute(select(BillingPlan).order_by(BillingPlan.price_usd_cents.asc()))
    return list(result.scalars().all())


@router.post("/plans", response_model=BillingPlanOut)
async def create_plan(
    body: BillingPlanCreate,
    session: AsyncSession = Depends(get_session),
    _: UserClaims = Depends(require_platform_superadmin),
):
    dup = await session.execute(select(BillingPlan.id).where(BillingPlan.slug == body.slug).limit(1))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Plan slug already in use")
    plan = BillingPlan(**body.model_dump())
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


@router.patch("/plans/{plan_id}", response_model=BillingPlanOut)
async def patch_plan(
    plan_id: UUID,
    body: BillingPlanPatch,
    session: AsyncSession = Depends(get_session),
    _: UserClaims = Depends(require_platform_superadmin),
):
    plan = await session.get(BillingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await session.commit()
    await session.refresh(plan)
    return plan


# ---------------------------------------------------------------------------
# Tenant billing routes
# ---------------------------------------------------------------------------


@router.get("/tenants/{tenant_id}", response_model=TenantBillingOut)
async def get_tenant_billing(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    await assert_msp_or_platform_can_touch_tenant(session, user, tenant_id)

    r = await session.execute(select(TenantBilling).where(TenantBilling.tenant_id == tenant_id).limit(1))
    billing = r.scalar_one_or_none()
    if billing is None:
        now = datetime.now(timezone.utc)
        billing = TenantBilling(
            tenant_id=tenant_id,
            api_calls_today=0,
            log_volume_mb_today=0,
            updated_at=now,
            created_at=now,
        )

    plan = await session.get(BillingPlan, billing.plan_id) if billing.plan_id else None
    return _billing_out(billing, plan)


@router.put("/tenants/{tenant_id}", response_model=TenantBillingOut)
async def upsert_tenant_billing(
    tenant_id: UUID,
    body: TenantBillingUpsert,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    await assert_msp_or_platform_can_touch_tenant(session, user, tenant_id)

    if body.plan_id:
        plan = await session.get(BillingPlan, body.plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan not found")

    r = await session.execute(select(TenantBilling).where(TenantBilling.tenant_id == tenant_id).limit(1))
    billing = r.scalar_one_or_none()
    if billing is None:
        billing = TenantBilling(tenant_id=tenant_id)
        session.add(billing)
        await session.flush()

    if "plan_id" in body.model_fields_set:
        billing.plan_id = body.plan_id
    if "notes" in body.model_fields_set:
        billing.notes = body.notes

    await session.commit()
    await session.refresh(billing)

    plan = await session.get(BillingPlan, billing.plan_id) if billing.plan_id else None
    return _billing_out(billing, plan)


@router.post("/tenants/{tenant_id}/reset-counters")
async def reset_billing_counters(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    await assert_msp_or_platform_can_touch_tenant(session, user, tenant_id)

    r = await session.execute(select(TenantBilling).where(TenantBilling.tenant_id == tenant_id).limit(1))
    billing = r.scalar_one_or_none()
    if billing:
        billing.api_calls_today = 0
        billing.log_volume_mb_today = 0
        await session.commit()
    return {"ok": True}
