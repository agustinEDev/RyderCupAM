"""
CSRF Protection Configuration

Configuración para la protección contra Cross-Site Request Forgery (CSRF).
Estrategia de triple capa:
1. Custom Header X-CSRF-Token (principal)
2. Double-Submit Cookie csrf_token (NO httpOnly)
3. SameSite="lax" (ya implementado en cookies)

Tokens: `aleatorio.firma` (BE #724). El aleatorio son 256 bits
(secrets.token_urlsafe(32)); la firma, HMAC-SHA256 del usuario y el aleatorio con
una clave derivada de SECRET_KEY. Sin la firma, quien pudiera escribir una cookie
en el dominio padre («cookie tossing») elegía cabecera y cookie a la vez.
Duración: 15 minutos (igual que access tokens)
"""

import base64
import functools
import hashlib
import hmac
import secrets
from typing import Final

from src.config.settings import settings

# Token generation
TOKEN_LENGTH: Final[int] = 32  # 32 bytes = 256 bits

# La etiqueta separa esta clave de cualquier otro uso de SECRET_KEY: una firma
# CSRF no vale como nada más (Agustín, 4 nov 2026: derivada, sin variable nueva)
_ETIQUETA_DE_LA_CLAVE: Final[bytes] = b"rydercupfriends:csrf-token:v1"


@functools.cache
def _clave() -> bytes:
    """La clave de las firmas CSRF, derivada de SECRET_KEY con su etiqueta."""
    return hmac.new(settings.SECRET_KEY.encode(), _ETIQUETA_DE_LA_CLAVE, hashlib.sha256).digest()


def _en_base64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _firma(user_id: str, aleatorio: str) -> str:
    mensaje = f"{user_id}!{aleatorio}".encode()
    return _en_base64(hmac.new(_clave(), mensaje, hashlib.sha256).digest())


def generate_csrf_token(user_id: str) -> str:
    """
    Genera un token CSRF firmado para ese usuario (BE #724).

    Args:
        user_id: El id del usuario de la sesión que lo recibe

    Returns:
        str: `aleatorio.firma`, los dos en base64 URL
    """
    aleatorio = secrets.token_urlsafe(TOKEN_LENGTH)
    return f"{aleatorio}.{_firma(user_id, aleatorio)}"


def csrf_token_belongs_to(token: str, user_id: str) -> bool:
    """¿Lleva el token la firma de ese usuario? Comparación de tiempo constante."""
    partes = token.split(".")
    if len(partes) != 2 or not all(partes):  # noqa: PLR2004 - aleatorio y firma
        return False
    aleatorio, firma = partes
    # En bytes: con texto no ASCII, `compare_digest` lanza TypeError (revisor)
    return hmac.compare_digest(firma.encode(), _firma(user_id, aleatorio).encode())


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
    "/api/v1/support/contact",  # Public endpoint - no existing session
    "/api/v1/auth/google",  # Public endpoint - Google OAuth login/register
}


def es_ruta_exenta(path: str) -> bool:
    """
    Exenta solo si es EXACTAMENTE una de la lista (BE #724). Por prefijo,
    `/api/v1/auth/google/link` y `/google/unlink` —con sesión— colgaban de
    `/api/v1/auth/google`, y cualquier ruta nueva que empezara igual quedaba
    exenta sin que nadie lo decidiera.
    """
    return path in EXEMPT_PATHS


# Exempt methods (métodos seguros según RFC 7231)
EXEMPT_METHODS: Final[set[str]] = {"GET", "HEAD", "OPTIONS"}
