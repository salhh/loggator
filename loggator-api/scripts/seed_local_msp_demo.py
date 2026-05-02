#!/usr/bin/env python3
"""
Idempotent demo data for local Docker / MSP + support testing.

Creates (if missing):
  - Customer tenant `demo-msp-customer` under the existing operator tenant (from migration backfill)
  - User `msp@local` with msp_admin on the operator tenant (password login, display_name set)
  - User `customer@local` with tenant_member on the demo customer tenant (display_name set)
  - One support thread + customer message on the demo tenant (matches SupportThread / SupportMessage schema)

Env (optional):
  SEED_MSP_EMAIL, SEED_MSP_PASSWORD, SEED_MSP_DISPLAY_NAME,
  SEED_CUSTOMER_EMAIL, SEED_CUSTOMER_PASSWORD, SEED_CUSTOMER_DISPLAY_NAME
"""
from __future__ import annotations

import asyncio
import os
import sys

# Ensure repo root on path when run as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.password_hashing import hash_password
from loggator.db.models import Membership, SupportMessage, SupportThread, Tenant, User
from loggator.db.session import AsyncSessionLocal


async def _ensure_user(
    session: AsyncSession,
    subject: str,
    email: str,
    password: str,
    *,
    display_name: str,
) -> User:
    r = await session.execute(select(User).where(User.subject == subject).limit(1))
    u = r.scalar_one_or_none()
    digest = hash_password(password)
    if u is None:
        u = User(subject=subject, email=email, password_hash=digest, display_name=display_name)
        session.add(u)
        await session.flush()
    else:
        if u.password_hash is None:
            u.password_hash = digest
        if email:
            u.email = email
        if not u.display_name:
            u.display_name = display_name
    return u


async def _ensure_membership(session: AsyncSession, user_id, tenant_id, role: str) -> None:
    q = select(Membership).where(
        Membership.user_id == user_id,
        Membership.tenant_id == tenant_id,
        Membership.role == role,
    )
    ex = await session.execute(q.limit(1))
    if ex.scalar_one_or_none() is None:
        session.add(Membership(user_id=user_id, tenant_id=tenant_id, role=role))


async def main() -> None:
    msp_email = (os.environ.get("SEED_MSP_EMAIL") or "msp@local").strip().lower()
    msp_pw = (os.environ.get("SEED_MSP_PASSWORD") or "msp-admin-demo").strip()
    msp_name = (os.environ.get("SEED_MSP_DISPLAY_NAME") or "MSP Demo Admin").strip()
    cust_email = (os.environ.get("SEED_CUSTOMER_EMAIL") or "customer@local").strip().lower()
    cust_pw = (os.environ.get("SEED_CUSTOMER_PASSWORD") or "customer-demo").strip()
    cust_name = (os.environ.get("SEED_CUSTOMER_DISPLAY_NAME") or "Demo Customer").strip()

    async with AsyncSessionLocal() as session:
        r = await session.execute(
            select(Tenant).where(Tenant.is_operator.is_(True), Tenant.deleted_at.is_(None)).limit(1)
        )
        op = r.scalar_one_or_none()
        if op is None:
            print("seed_local_msp_demo: no operator tenant found; run migrations first.", file=sys.stderr)
            sys.exit(1)

        r2 = await session.execute(select(Tenant).where(Tenant.slug == "demo-msp-customer").limit(1))
        cust = r2.scalar_one_or_none()
        if cust is None:
            cust = Tenant(
                name="Demo MSP Customer",
                slug="demo-msp-customer",
                status="active",
                parent_tenant_id=op.id,
                is_operator=False,
            )
            session.add(cust)
            await session.flush()
            print("seed_local_msp_demo: created tenant demo-msp-customer", flush=True)
        else:
            print("seed_local_msp_demo: tenant demo-msp-customer already exists", flush=True)

        msp_subject = f"local:{msp_email}"
        msp_user = await _ensure_user(
            session, msp_subject, msp_email, msp_pw, display_name=msp_name
        )
        await _ensure_membership(session, msp_user.id, op.id, "msp_admin")
        print(f"seed_local_msp_demo: MSP user {msp_email} (msp_admin on operator)", flush=True)

        cust_subject = f"local:{cust_email}"
        cust_user = await _ensure_user(
            session, cust_subject, cust_email, cust_pw, display_name=cust_name
        )
        await _ensure_membership(session, cust_user.id, cust.id, "tenant_member")
        print(f"seed_local_msp_demo: customer user {cust_email} (member of demo-msp-customer)", flush=True)

        r_th = await session.execute(
            select(SupportThread).where(SupportThread.tenant_id == cust.id).limit(1)
        )
        if r_th.scalar_one_or_none() is None:
            th = SupportThread(
                tenant_id=cust.id,
                operator_tenant_id=op.id,
                created_by_user_id=cust_user.id,
                subject="Seeded support thread",
                status="open",
            )
            session.add(th)
            await session.flush()
            session.add(
                SupportMessage(
                    thread_id=th.id,
                    author_user_id=cust_user.id,
                    body="Hello — this thread was created by seed_local_msp_demo.py",
                    is_staff=False,
                )
            )
            print("seed_local_msp_demo: created support thread + message", flush=True)
        else:
            print("seed_local_msp_demo: support thread already exists for demo tenant", flush=True)

        await session.commit()

    print("", flush=True)
    print("--- Demo logins (password auth) ---", flush=True)
    print(f"  MSP operator console:  {msp_email}  /  {msp_pw}", flush=True)
    print(f"  Customer (tenant bar → Demo MSP Customer):  {cust_email}  /  {cust_pw}", flush=True)
    print(f"  Platform admin (if bootstrapped):  admin@local  /  (BOOTSTRAP_LOCAL_ADMIN_PASSWORD)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
