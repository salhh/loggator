"""
IAM client — JWT/OIDC verifier.

Supports:
- OIDC RS256 tokens verified via JWKS (issuer/audience configurable)
- Optional dev-only HS256 verification via DEV_JWT_SECRET
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from jose import jwt
from jose.exceptions import JOSEError

from loggator.auth.schemas import UserClaims
from loggator.config import settings


@dataclass
class _JWKSCache:
    keys: dict[str, Any]
    fetched_at: float


class IAMClient:
    """
    Client for the external IAM service.

    Stub implementation — replace with actual HTTP calls to IAM service.
    Environment variables needed (add to config.py and .env.prod.example):
      - IAM_BASE_URL: Base URL of the IAM service
      - IAM_CLIENT_ID: Client ID for this application
      - IAM_CLIENT_SECRET: Client secret for token validation
    """

    def __init__(self) -> None:
        self._jwks: _JWKSCache | None = None

    async def _get_jwks(self) -> dict[str, Any]:
        # cache for 10 minutes
        if self._jwks and (time.time() - self._jwks.fetched_at) < 600:
            return self._jwks.keys

        jwks_url = settings.oidc_jwks_url.strip()
        issuer = settings.oidc_issuer.strip().rstrip("/")
        if not jwks_url and issuer:
            jwks_url = f"{issuer}/.well-known/jwks.json"
        if not jwks_url:
            raise ValueError("OIDC_JWKS_URL (or OIDC_ISSUER) must be set when AUTH_DISABLED=false.")

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            jwks = resp.json()

        keys = {k.get("kid", ""): k for k in jwks.get("keys", []) if k.get("kid")}
        self._jwks = _JWKSCache(keys=keys, fetched_at=time.time())
        return keys

    def _claims_to_user(self, claims: dict[str, Any]) -> UserClaims:
        sub = str(claims.get("sub") or claims.get("user_id") or "")
        email = str(claims.get("email") or claims.get("upn") or claims.get("preferred_username") or "")

        roles = claims.get("roles") or claims.get("tenant_roles") or []
        if isinstance(roles, str):
            roles = [roles]

        platform_roles = claims.get("platform_roles") or claims.get("platformRoles") or []
        if isinstance(platform_roles, str):
            platform_roles = [platform_roles]

        tenant_id = claims.get("tenant_id") or claims.get("tenantId")
        tenant_ids = claims.get("tenant_ids") or claims.get("tenantIds") or []
        parsed_tenant_id: UUID | None = None
        parsed_tenant_ids: list[UUID] = []

        if tenant_id:
            try:
                parsed_tenant_id = UUID(str(tenant_id))
            except ValueError:
                parsed_tenant_id = None

        if isinstance(tenant_ids, (list, tuple)):
            for t in tenant_ids:
                try:
                    parsed_tenant_ids.append(UUID(str(t)))
                except ValueError:
                    continue

        raw_ot = claims.get("operator_tenant_id") or claims.get("operatorTenantId")
        parsed_operator: UUID | None = None
        if raw_ot:
            try:
                parsed_operator = UUID(str(raw_ot))
            except ValueError:
                parsed_operator = None

        skip = {
            "sub",
            "email",
            "roles",
            "platform_roles",
            "tenant_id",
            "tenant_ids",
            "operator_tenant_id",
            "operatorTenantId",
        }
        return UserClaims(
            user_id=sub,
            email=email,
            roles=list(roles) if isinstance(roles, list) else [],
            platform_roles=list(platform_roles) if isinstance(platform_roles, list) else [],
            tenant_id=parsed_tenant_id,
            tenant_ids=parsed_tenant_ids,
            operator_tenant_id=parsed_operator,
            **{k: v for k, v in claims.items() if k not in skip},
        )

    async def verify_token(self, token: str) -> UserClaims | None:
        """
        Verify a bearer token.

        Returns UserClaims if the token is valid, None if invalid/expired.
        """
        # Dev-only HS256
        dev_secret = settings.dev_jwt_secret.get_secret_value().strip()
        if dev_secret:
            try:
                claims = jwt.decode(
                    token,
                    dev_secret,
                    algorithms=["HS256"],
                    audience=settings.oidc_audience or None,
                    issuer=settings.oidc_issuer or None,
                    options={"verify_aud": bool(settings.oidc_audience), "verify_iss": bool(settings.oidc_issuer)},
                )
                return self._claims_to_user(claims)
            except JOSEError:
                return None

        # OIDC RS256 using JWKS
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                return None
            jwks = await self._get_jwks()
            key = jwks.get(kid)
            if not key:
                # refresh once in case of key rotation
                self._jwks = None
                jwks = await self._get_jwks()
                key = jwks.get(kid)
                if not key:
                    return None

            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256", "ES256"],
                audience=settings.oidc_audience or None,
                issuer=settings.oidc_issuer or None,
                options={"verify_aud": bool(settings.oidc_audience), "verify_iss": bool(settings.oidc_issuer)},
            )
            return self._claims_to_user(claims)
        except (JOSEError, ValueError):
            return None

    async def get_user_info(self, user_id: str) -> UserClaims | None:
        """
        Fetch user information from the IAM service.

        TODO: implement with actual IAM HTTP calls.
        """
        # Placeholder: no implementation
        return None
