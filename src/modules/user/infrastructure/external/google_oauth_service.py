"""
Google OAuth Service - Infrastructure Layer

Implementación del servicio de Google OAuth usando httpx.
Intercambia authorization codes por información del usuario.
"""

import logging

import httpx

from src.config.settings import settings
from src.modules.user.application.ports.google_oauth_service_interface import (
    GoogleUserInfo,
    IGoogleOAuthService,
)

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
HTTP_OK = 200


class GoogleOAuthService(IGoogleOAuthService):
    """
    Implementación de IGoogleOAuthService usando httpx.

    Flujo:
    1. POST a Google token endpoint para intercambiar code por access_token
    2. GET a Google userinfo endpoint para obtener datos del usuario
    """

    async def exchange_code_for_user_info(self, authorization_code: str) -> GoogleUserInfo:
        """
        Intercambia un authorization code de Google por información del usuario.

        Args:
            authorization_code: Código de Google OAuth

        Returns:
            GoogleUserInfo con datos del usuario

        Raises:
            ValueError: Si el código es inválido, expirado, o Google API falla
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Exchange code for tokens
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": authorization_code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )

            if token_response.status_code != HTTP_OK:
                logger.warning(
                    f"Google token exchange failed: {token_response.status_code} - "
                    f"{token_response.text[:200]}"
                )
                raise ValueError("Invalid or expired Google authorization code")

            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError("Google did not return an access token")

            # 2. Get user info
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if userinfo_response.status_code != HTTP_OK:
                logger.warning(
                    f"Google userinfo request failed: {userinfo_response.status_code}"
                )
                raise ValueError("Failed to retrieve user information from Google")

            userinfo = userinfo_response.json()

            google_user_id = userinfo.get("sub")
            email = userinfo.get("email")
            if not google_user_id or not email:
                raise ValueError("Google user info is missing required fields (sub, email)")

            return GoogleUserInfo(
                google_user_id=google_user_id,
                email=email,
                first_name=userinfo.get("given_name", ""),
                last_name=userinfo.get("family_name", ""),
                picture_url=userinfo.get("picture"),
            )
