"""
CSRF Protection Configuration

Configuración para la protección contra Cross-Site Request Forgery (CSRF).
Estrategia de triple capa:
1. Custom Header X-CSRF-Token (principal)
2. Double-Submit Cookie csrf_token (NO httpOnly)
3. SameSite="lax" (ya implementado en cookies)

Tokens: 256 bits (secrets.token_urlsafe(32))
Duración: 15 minutos (igual que access tokens)
"""

import secrets
from typing import Final

# Token generation
TOKEN_LENGTH: Final[int] = 32  # 32 bytes = 256 bits


def generate_csrf_token() -> str:
    """
    Genera un token CSRF seguro de 256 bits.

    Returns:
        str: Token CSRF URL-safe base64
    """
    return secrets.token_urlsafe(TOKEN_LENGTH)


# Cookie configuration
CSRF_COOKIE_NAME: Final[str] = "csrf_token"
CSRF_COOKIE_MAX_AGE: Final[int] = 900  # 15 minutos (igual que access token)
CSRF_COOKIE_HTTPONLY: Final[bool] = False  # Debe ser accesible desde JS
CSRF_COOKIE_SECURE: Final[bool] = True  # Solo HTTPS en producción
CSRF_COOKIE_SAMESITE: Final[str] = "lax"  # Protección adicional

# Header configuration
CSRF_HEADER_NAME: Final[str] = "X-CSRF-Token"

# Exempt paths (no requieren validación CSRF)
EXEMPT_PATHS: Final[set[str]] = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/register",  # Public endpoint - no existing session
    "/api/v1/auth/login",  # Public endpoint - generates CSRF token
    "/api/v1/auth/refresh-token",  # Protected by httpOnly refresh_token cookie
    "/api/v1/auth/logout",  # Session termination - low risk, high usability
    "/api/v1/auth/forgot-password",  # Public endpoint
    "/api/v1/auth/reset-password",  # Public endpoint (token in URL)
    "/api/v1/auth/verify-email",  # Public endpoint (token in URL)
}

# Exempt methods (métodos seguros según RFC 7231)
EXEMPT_METHODS: Final[set[str]] = {"GET", "HEAD", "OPTIONS"}
