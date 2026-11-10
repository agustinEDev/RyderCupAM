"""
CSRF Protection Configuration

Configuración para la protección contra Cross-Site Request Forgery (CSRF).
Estrategia de triple capa:
1. Custom Header X-CSRF-Token (principal)
2. Double-Submit Cookie csrf_token (NO httpOnly)
3. SameSite="lax" (ya implementado en cookies)

Tokens: `aleatorio.emitido.firma` (BE #724 y F-19). El aleatorio son 256 bits
(secrets.token_urlsafe(32)); `emitido`, la hora de emisión en segundos Unix; la
firma, HMAC-SHA256 del usuario, el aleatorio y la hora con una clave derivada de
SECRET_KEY. Sin la firma, quien pudiera escribir una cookie en el dominio padre
(«cookie tossing») elegía cabecera y cookie a la vez.

Caducidad (F-19, auditoría OWASP del 9 nov 2026): la cookie dura 15 minutos, pero el
token en sí valía para siempre. Ahora vale lo que el refresh token
(REFRESH_TOKEN_EXPIRE_DAYS) más una hora: cada login y cada refresco emiten uno
nuevo, así que ninguna sesión viva usa uno más viejo. La hora de margen cubre la
diferencia de reloj entre dos instancias durante un despliegue y una petición en
vuelo; más no hace falta, porque el front recupera un 403 CSRF refrescando.

Los tokens del formato anterior (`aleatorio.firma`, sin hora) no valen: no se sabe
cuándo se emitieron. Nadie pierde la sesión al desplegar: ante un 403
CSRF_VALIDATION_FAILED el front refresca (lo que emite uno nuevo, con hora) y repite
la petición una vez (hotfix FE 2.63.1); solo cierra la sesión si el refresco falla.
"""

import base64
import functools
import hashlib
import hmac
import secrets
import time
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


# El margen sobre la vida del refresh token (ver el docstring del módulo)
MARGEN_DE_CADUCIDAD_S: Final[int] = 60 * 60
# Una hora Unix en segundos tiene 10 cifras hasta el año 2286; más es basura
_MAX_CIFRAS_DE_LA_HORA: Final[int] = 12


def vida_del_token_csrf() -> int:
    """Segundos que vale un token CSRF: la vida del refresh token más el margen."""
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60 + MARGEN_DE_CADUCIDAD_S


def _firma(user_id: str, aleatorio: str, emitido: str) -> str:
    """HMAC-SHA256 de usuario, aleatorio y hora de emisión, en base64 URL."""
    mensaje = f"{user_id}!{aleatorio}!{emitido}".encode()
    return _en_base64(hmac.new(_clave(), mensaje, hashlib.sha256).digest())


def generate_csrf_token(user_id: str, *, ahora: float | None = None) -> str:
    """
    Genera un token CSRF firmado para ese usuario, con su hora (BE #724, F-19).

    Args:
        user_id: El id del usuario de la sesión que lo recibe
        ahora: La hora de emisión (segundos Unix); por defecto, la del reloj

    Returns:
        str: `aleatorio.emitido.firma`; aleatorio y firma en base64 URL
    """
    aleatorio = secrets.token_urlsafe(TOKEN_LENGTH)
    emitido = str(int(time.time() if ahora is None else ahora))
    return f"{aleatorio}.{emitido}.{_firma(user_id, aleatorio, emitido)}"


def csrf_token_belongs_to(token: str, user_id: str, *, ahora: float | None = None) -> bool:
    """
    ¿Lleva el token la firma de ese usuario y sigue vigente? Comparación de tiempo
    constante. Uno sin hora (el formato de BE #724) no vale.

    Args:
        token: El token de la cabecera X-CSRF-Token
        user_id: El usuario de la sesión
        ahora: La hora con la que se mide la edad; por defecto, la del reloj
    """
    partes = token.split(".")
    if len(partes) != 3 or not all(partes):  # noqa: PLR2004 - aleatorio, hora y firma
        return False
    aleatorio, emitido, firma = partes
    # Solo cifras ASCII: int() aceptaría «١٢٣», « 1» o «1_0»
    if not (emitido.isascii() and emitido.isdigit()) or len(emitido) > _MAX_CIFRAS_DE_LA_HORA:
        return False
    # En bytes: con texto no ASCII, `compare_digest` lanza TypeError (revisor)
    if not hmac.compare_digest(firma.encode(), _firma(user_id, aleatorio, emitido).encode()):
        return False
    edad = (time.time() if ahora is None else ahora) - int(emitido)
    return -MARGEN_DE_CADUCIDAD_S <= edad <= vida_del_token_csrf()


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
    # Los enlaces del correo, sin sesión (fase 3): validar el de restablecer y pedir otro
    # de verificación desde la pantalla de «enlace caducado». Públicas, con su límite y
    # la misma respuesta exista o no la cuenta
    "/api/v1/auth/validate-reset-token",
    "/api/v1/auth/resend-verification",
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
    # Sin la barra final: `/login/` es `/login` (code-review)
    return (path.rstrip("/") or "/") in EXEMPT_PATHS


# Exempt methods (métodos seguros según RFC 7231)
EXEMPT_METHODS: Final[set[str]] = {"GET", "HEAD", "OPTIONS"}
