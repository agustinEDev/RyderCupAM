"""
Sentry User Context Middleware (v1.8.0 - Task 10)

Middleware para capturar contexto de usuario en eventos de Sentry.

Funcionalidad:
- Extrae JWT token de cookies o headers (Authorization)
- Decodifica el token para obtener user_id y email
- Establece contexto de usuario en Sentry (sentry_sdk.set_user)
- Silencioso: Si falla la decodificación, continúa sin usuario (request anónimo)

Contexto capturado:
- id: UUID del usuario
- email: Email del usuario
- ip_address: IP del cliente (X-Forwarded-For o X-Real-IP)

Beneficios:
- Errores en Sentry muestran qué usuario fue afectado
- Facilita debugging y soporte al usuario
- Permite identificar patrones de errores por usuario

OWASP Coverage:
- A09: Logging & Monitoring (contexto completo en eventos)
"""

import logging

import sentry_sdk
from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.settings import settings

logger = logging.getLogger(__name__)


class SentryUserContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware para añadir contexto de usuario a eventos de Sentry.

    Extrae información del token JWT (si existe) y la registra en Sentry.
    Si no hay token o es inválido, el request se procesa como anónimo.
    """

    def _extract_token_from_request(self, request: Request) -> str | None:
        """
        Extrae el token JWT del request.

        Orden de prioridad:
        1. Cookie httpOnly "access_token"
        2. Header Authorization "Bearer <token>"

        Args:
            request: Request de FastAPI

        Returns:
            Token JWT o None si no se encuentra
        """
        # 1. Intentar cookie httpOnly (prioridad 1)
        token = request.cookies.get("access_token")
        if token:
            return token

        # 2. Intentar header Authorization (backward compatibility)
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            return authorization.replace("Bearer ", "")

        return None

    def _decode_token(self, token: str) -> dict | None:
        """
        Decodifica el token JWT para extraer el payload.

        Args:
            token: Token JWT

        Returns:
            Payload del token o None si falla la decodificación
        """
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            return payload
        except JWTError as e:
            logger.debug(f"Failed to decode JWT token for Sentry context: {e}")
            return None

    def _get_client_ip(self, request: Request) -> str | None:
        """
        Extrae la IP del cliente del request.

        Orden de prioridad:
        1. X-Forwarded-For (proxy/load balancer)
        2. X-Real-IP (Nginx)
        3. request.client.host (directo)

        Args:
            request: Request de FastAPI

        Returns:
            IP del cliente o None
        """
        # X-Forwarded-For puede contener múltiples IPs: "client, proxy1, proxy2"
        # Tomamos la primera (IP real del cliente)
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        # X-Real-IP header usado por Nginx
        x_real_ip = request.headers.get("X-Real-IP")
        if x_real_ip:
            return x_real_ip

        # Fallback: IP directa del cliente
        if request.client:
            return request.client.host

        return None

    async def dispatch(self, request: Request, call_next):
        """
        Procesa el request y añade contexto de usuario a Sentry.

        Args:
            request: Request de FastAPI
            call_next: Siguiente middleware/handler en la cadena

        Returns:
            Response del handler
        """
        # Extraer token JWT del request
        token = self._extract_token_from_request(request)

        if token:
            # Decodificar token para obtener user_id y email
            payload = self._decode_token(token)

            if payload:
                # Establecer contexto de usuario en Sentry
                sentry_sdk.set_user(
                    {
                        "id": payload.get("sub"),  # UUID del usuario
                        "email": payload.get("email"),  # Email del usuario
                        "ip_address": self._get_client_ip(request),  # IP del cliente
                    }
                )
            else:
                # Token inválido o expirado -> request anónimo
                sentry_sdk.set_user(None)
        else:
            # Sin token -> request anónimo
            sentry_sdk.set_user(None)

        # Procesar el request
        response = await call_next(request)

        # Limpiar contexto de usuario para el siguiente request
        sentry_sdk.set_user(None)

        return response
