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

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # nosec B105 - not a password, it's the Google OAuth endpoint URL
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
        try:
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

                first_name, last_name = self._resolve_names(userinfo, email)

                return GoogleUserInfo(
                    google_user_id=google_user_id,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    email_verified=bool(userinfo.get("email_verified", False)),
                    picture_url=userinfo.get("picture"),
                )
        except ValueError:
            raise
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.warning(f"Google OAuth network error: {exc}")
            raise ValueError(f"Failed to communicate with Google OAuth service: {exc}") from exc

    @staticmethod
    def _resolve_names(userinfo: dict, email: str) -> tuple[str, str]:
        """
        Nombre y apellido de un perfil de Google, que no siempre los trae.

        Google manda `given_name` y `family_name` solo cuando la cuenta tiene
        el nombre estructurado. Una cuenta con un solo nombre manda `name` y
        nada más, y antes eso se guardaba como cadena vacía: el registro se
        cerraba con el nombre en blanco y el cliente rechazaba la respuesta al
        pintarla, así que la cuenta quedaba creada y **sin poder entrar nunca**
        —el siguiente intento la encuentra por su cuenta de Google y devuelve
        el mismo nombre vacío—.

        Se cae primero a `name`, partiéndolo en nombre y apellidos, y en último
        término a la parte local del email: un dato real del usuario, no uno
        inventado, y que además va a corregir en el acto, porque un registro
        nuevo aterriza en «completar perfil».
        """
        given = (userinfo.get("given_name") or "").strip()
        family = (userinfo.get("family_name") or "").strip()
        if given and family:
            return given, family

        # "Ada Lovelace King" → nombre "Ada", apellidos "Lovelace King"
        full_name_parts = (userinfo.get("name") or "").split()
        if not given and full_name_parts:
            given = full_name_parts[0]
        if not family and len(full_name_parts) > 1:
            family = " ".join(full_name_parts[1:])

        # El email ya viene validado como no vacío, pero un local vacío
        # ("@dominio") dejaría el mismo hueco que se está cerrando
        fallback = email.split("@", 1)[0].strip() or "Usuario"
        return given or fallback, family or fallback

