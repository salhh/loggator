"""Pydantic schemas for authentication claims."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class UserClaims(BaseModel):
    """
    Represents the claims extracted from a verified IAM token.

    Fields will be populated once the IAM integration is implemented.
    """
    user_id: str = Field(..., description="Unique user identifier from IAM")
    email: str = Field(..., description="User's email address")
    roles: list[str] = Field(default_factory=list, description="User's assigned roles")

    class Config:
        # Allow extra fields from IAM token claims
        extra = "allow"
