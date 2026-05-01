"""POST /auth/login — username + password, returns HS256 JWT when DEV_JWT_SECRET is set."""

from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.local_password import find_password_user, issue_access_token
from loggator.auth.password_hashing import verify_password
from loggator.config import settings
from loggator.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Email or subject for a password-enabled user")
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
async def login_with_password(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    if not settings.dev_jwt_secret.get_secret_value().strip():
        raise HTTPException(
            status_code=503,
            detail="Password login is not configured (set DEV_JWT_SECRET on the API).",
        )

    user = await find_password_user(session, body.username)
    if user is None or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = await issue_access_token(session, user)
    return LoginResponse(access_token=token)
