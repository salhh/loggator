"""Pydantic schemas for authentication claims."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID


class UserClaims(BaseModel):
    """
    Represents the claims extracted from a verified IAM token.

    Fields will be populated once the IAM integration is implemented.
    """
    model_config = ConfigDict(extra="allow")

    user_id: str = Field(..., description="Unique user identifier from IAM (usually OIDC sub)")
    email: str = Field(default="", description="User's email address")
    roles: list[str] = Field(default_factory=list, description="Tenant roles (tenant_admin, tenant_member)")
    platform_roles: list[str] = Field(default_factory=list, description="Platform roles (platform_admin)")

    # Tenant context: either a single tenant_id claim, or multiple tenant_ids.
    tenant_id: Optional[UUID] = Field(default=None, description="Active tenant ID (single-tenant token)")
    tenant_ids: list[UUID] = Field(default_factory=list, description="Tenants this principal can access")
