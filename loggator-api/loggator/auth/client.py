"""
IAM client — placeholder for external IAM service integration.

TODO: Implement once IAM service documentation is provided.
Required implementation:
  - verify_token(token: str) -> UserClaims
  - get_user_info(user_id: str) -> UserClaims
"""

from __future__ import annotations

from loggator.auth.schemas import UserClaims


class IAMClient:
    """
    Client for the external IAM service.

    Stub implementation — replace with actual HTTP calls to IAM service.
    Environment variables needed (add to config.py and .env.prod.example):
      - IAM_BASE_URL: Base URL of the IAM service
      - IAM_CLIENT_ID: Client ID for this application
      - IAM_CLIENT_SECRET: Client secret for token validation
    """

    async def verify_token(self, token: str) -> UserClaims | None:
        """
        Verify a bearer token with the IAM service.

        Returns UserClaims if the token is valid, None if invalid/expired.
        TODO: implement with actual IAM HTTP calls.
        """
        # Placeholder: no verification
        return None

    async def get_user_info(self, user_id: str) -> UserClaims | None:
        """
        Fetch user information from the IAM service.

        TODO: implement with actual IAM HTTP calls.
        """
        # Placeholder: no implementation
        return None
