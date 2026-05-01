"""Local username/password login: DB user + HS256 JWT (DEV_JWT_SECRET)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import jwt
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.password_hashing import hash_password, verify_password
from loggator.config import settings
from loggator.db.models import Membership, Tenant, User
from loggator.tenancy.bootstrap import get_default_tenant_id


async def find_password_user(session: AsyncSession, login: str) -> User | None:
    """Match email (case-insensitive), exact subject, or local:{email} subject."""
    raw = login.strip()
    if not raw:
        return None
    lowered = raw.lower()
    r = await session.execute(
        select(User)
        .where(
            User.password_hash.is_not(None),
            or_(
                func.lower(User.email) == lowered,
                User.subject == raw,
                User.subject == f"local:{lowered}",
            ),
        )
        .limit(1)
    )
    return r.scalar_one_or_none()


async def _jwt_claims_from_memberships(session: AsyncSession, user: User) -> tuple[list[str], list[str], list[UUID], UUID | None]:
    mr = await session.execute(
        select(Membership, Tenant)
        .outerjoin(Tenant, Tenant.id == Membership.tenant_id)
        .where(Membership.user_id == user.id)
    )
    platform_roles: list[str] = []
    roles: list[str] = []
    tenant_ids: list[UUID] = []
    operator_tenant_id: UUID | None = None
    seen_pf: set[str] = set()
    seen_msp = False
    seen_r: set[str] = set()
    seen_t: set[UUID] = set()

    for m, t in mr.all():
        if m.tenant_id and m.tenant_id not in seen_t:
            tenant_ids.append(m.tenant_id)
            seen_t.add(m.tenant_id)
        if m.role == "platform_admin" and m.tenant_id is None and "platform_admin" not in seen_pf:
            platform_roles.append("platform_admin")
            seen_pf.add("platform_admin")
        if m.role == "msp_admin" and t is not None and t.is_operator and not seen_msp:
            platform_roles.append("msp_admin")
            seen_msp = True
            operator_tenant_id = m.tenant_id
        if m.role in ("tenant_admin", "tenant_member") and m.role not in seen_r:
            roles.append(m.role)
            seen_r.add(m.role)
    return platform_roles, roles, tenant_ids, operator_tenant_id


async def issue_access_token(session: AsyncSession, user: User) -> str:
    secret = settings.dev_jwt_secret.get_secret_value().strip()
    if not secret:
        raise RuntimeError("DEV_JWT_SECRET is not set")

    platform_roles, roles, tenant_ids, operator_tenant_id = await _jwt_claims_from_memberships(session, user)

    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=24)
    payload: dict = {
        "sub": user.subject,
        "email": user.email or "",
        "platform_roles": platform_roles,
        "roles": roles,
        "tenant_ids": [str(t) for t in tenant_ids],
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if operator_tenant_id:
        payload["operator_tenant_id"] = str(operator_tenant_id)
    if settings.oidc_issuer:
        payload["iss"] = settings.oidc_issuer.strip().rstrip("/")
    if settings.oidc_audience:
        payload["aud"] = settings.oidc_audience.strip()

    return jwt.encode(payload, secret, algorithm="HS256")


async def ensure_bootstrap_password_admin(session: AsyncSession) -> None:
    """Create or update bootstrap admin when env vars and DEV_JWT_SECRET are set."""
    secret = settings.dev_jwt_secret.get_secret_value().strip()
    email = (settings.bootstrap_local_admin_email or "").strip()
    pw = settings.bootstrap_local_admin_password.get_secret_value().strip()
    if not secret or not email or not pw:
        return

    subject = f"local:{email.lower()}"
    r = await session.execute(select(User).where(User.subject == subject).limit(1))
    user = r.scalar_one_or_none()
    digest = hash_password(pw)
    if user is None:
        user = User(subject=subject, email=email, password_hash=digest)
        session.add(user)
        await session.flush()
    elif user.password_hash is None:
        user.password_hash = digest

    tenant_id = await get_default_tenant_id(session)

    async def _ensure_membership(tid: UUID | None, role: str) -> None:
        q = select(Membership).where(Membership.user_id == user.id, Membership.role == role)
        if tid is None:
            q = q.where(Membership.tenant_id.is_(None))
        else:
            q = q.where(Membership.tenant_id == tid)
        ex = await session.execute(q.limit(1))
        if ex.scalar_one_or_none() is None:
            session.add(Membership(user_id=user.id, tenant_id=tid, role=role))

    await _ensure_membership(tenant_id, "tenant_admin")
    await _ensure_membership(None, "platform_admin")
