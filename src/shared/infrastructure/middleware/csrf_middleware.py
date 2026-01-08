"""
CSRF Protection Middleware

Middleware para protección contra Cross-Site Request Forgery (CSRF).
Implementa validación de triple capa:

1. Custom Header X-CSRF-Token (principal)
2. Double-Submit Cookie csrf_token (NO httpOnly)
3. SameSite="lax" (ya implementado)

Valida POST, PUT, PATCH, DELETE.
Exime GET, HEAD, OPTIONS, rutas de health/docs.
"""

from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.csrf_config import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    EXEMPT_METHODS,
    EXEMPT_PATHS,
)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Middleware para validar tokens CSRF en requests no seguros.

    Estrategia:
    - Valida que header X-CSRF-Token y cookie csrf_token coincidan
    - Previene ataques CSRF mediante double-submit pattern
    - Timing-safe comparison para prevenir timing attacks
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Procesa el request validando CSRF token cuando sea necesario.

        Args:
            request: FastAPI request
            call_next: Siguiente middleware/handler

        Returns:
            Response: HTTP response (403 si CSRF inválido)
        """
        # Skip CSRF validation during integration tests (but not security tests)
        import os  # noqa: PLC0415 - Avoid circular import with config
        if os.getenv("TESTING") == "true" and os.getenv("TEST_CSRF") != "true":
            return await call_next(request)

        # Eximir métodos seguros (GET, HEAD, OPTIONS)
        if request.method in EXEMPT_METHODS:
            return await call_next(request)

        # Eximir rutas específicas (health, docs)
        path = request.url.path
        if any(path.startswith(exempt) for exempt in EXEMPT_PATHS):
            return await call_next(request)

        # Validar token CSRF
        if not self._validate_csrf_token(request):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "CSRF token missing or invalid",
                    "error_code": "CSRF_VALIDATION_FAILED",
                },
            )

        return await call_next(request)

    def _validate_csrf_token(self, request: Request) -> bool:
        """
        Valida que el token CSRF del header coincida con el de la cookie.

        Usa secrets.compare_digest para prevenir timing attacks.

        Args:
            request: FastAPI request

        Returns:
            bool: True si el token es válido
        """
        import secrets  # noqa: PLC0415 - Timing-safe comparison needed here

        # Obtener token del header
        header_token = request.headers.get(CSRF_HEADER_NAME)
        if not header_token:
            return False

        # Obtener token de la cookie
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        if not cookie_token:
            return False

        # Comparación timing-safe
        return secrets.compare_digest(header_token, cookie_token)
