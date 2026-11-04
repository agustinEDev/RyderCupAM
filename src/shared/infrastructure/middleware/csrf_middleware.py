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

import jwt
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from jwt.exceptions import InvalidTokenError
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.csrf_config import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    EXEMPT_METHODS,
    csrf_token_belongs_to,
    es_ruta_exenta,
)
from src.config.settings import settings
from src.shared.infrastructure.security.cookie_handler import (
    REFRESH_COOKIE_NAME,
    read_access_token,
)


def usuario_de_la_sesion(request: Request) -> str | None:
    """
    El usuario de la sesión de la petición, para exigir que el token CSRF sea
    suyo (BE #724). Del JWT de acceso —cookie o Bearer— y, si no, del de
    refresh. La firma del JWT SÍ se comprueba; la caducidad no: un acceso
    caducado sigue diciendo de quién es la sesión, y la petición ya dará su 401.

    Returns:
        El `sub`, o None si no hay sesión que suplantar.
    """
    for token in (read_access_token(request), request.cookies.get(REFRESH_COOKIE_NAME)):
        if not token:
            continue
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},
            )
        except InvalidTokenError:
            continue
        sub = payload.get("sub")
        if isinstance(sub, str) and sub:
            return sub
    return None


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
        if es_ruta_exenta(path):
            return await call_next(request)

        # Validar token CSRF: cabecera == cookie y, con sesión, firmado para ESE
        # usuario (BE #724). Sin sesión no hay a quién suplantar
        usuario = usuario_de_la_sesion(request)
        token = request.headers.get(CSRF_HEADER_NAME, "")
        if not self._validate_csrf_token(request) or (
            usuario is not None and not csrf_token_belongs_to(token, usuario)
        ):
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
        # En bytes: con texto no ASCII, `compare_digest` lanza TypeError y
        # la petición acababa en 500 en vez de 403 (revisor)
        return secrets.compare_digest(header_token.encode(), cookie_token.encode())
