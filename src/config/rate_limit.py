"""
Rate Limiting Configuration

Configuración centralizada de rate limiting para la API.

Quién cuenta en cada límite (RyderCupAM#273, ADR-038):

- **Rutas con sesión**: el usuario, sacado de un access token cuya firma se
  verifica. Es una identidad que pone el servidor: un token inventado no elige
  contador y cae en el de red.
- **Rutas anónimas**: la red (`get_client_identifier`), declarada en cada ruta. En
  producción es la IP real que da Cloudflare cuando la petición trae su secreto
  (ADR-041, BE #466), y una IPv6 cuenta por su /64. Sin el secreto, la del proxy de
  Render: un contador para toda la app, y por eso los topes siguen dimensionados
  para un club entero entrando a la vez.
- **Toda ruta sin límite propio**: DEFAULT_LIMIT, como dependencia global de la app
  (BE #467), salvo las de EXEMPT_FROM_DEFAULT_LIMIT.
- **Login, forgot-password y resend-verification**: además, por email, contado
  antes de saber si el email existe. Y el login, por red, solo cuenta los fallos:
  los aciertos de un club no lo cierran, y el credential stuffing, que casi solo
  falla, sí.

Ninguna clave sale de una cabecera que escriba el cliente (ADR-038): el secreto de
Cloudflare no lo conoce el cliente (ADR-041).
"""

import hashlib
import hmac
import ipaddress
import os

from limits import parse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.wrappers import Limit
from starlette.requests import Request

from src.config.settings import settings
from src.modules.user.domain.value_objects.email import Email, InvalidEmailError
from src.shared.infrastructure.http.http_context_validator import cloudflare_client_ip
from src.shared.infrastructure.security.cookie_handler import (
    get_refresh_cookie_name,
    read_access_token,
)
from src.shared.infrastructure.security.jwt_handler import (
    verify_access_token,
    verify_refresh_token,
)

# Topes de las rutas anónimas: por red, que en producción es toda la app
LOGIN_ATTEMPTS_LIMIT = "60/minute"  # techo de intentos: cada login cuesta un bcrypt
GOOGLE_LOGIN_LIMIT = "30/minute"
REGISTER_LIMIT = "30/hour"
EMAIL_SENDING_LIMIT = "30/hour"  # forgot-password y resend-verification
RESET_PASSWORD_LIMIT = "20/hour"  # nosec B105 - a rate limit, not a password
VALIDATE_RESET_TOKEN_LIMIT = "30/hour"  # nosec B105 - a rate limit, not a token
CONTACT_LIMIT = "10/hour"

REFRESH_TOKEN_LIMIT = "30/minute"  # nosec B105 - a rate limit, not a token
VERIFY_EMAIL_LIMIT = "30/hour"

# El de toda ruta sin límite propio (BE #467): por usuario con sesión, por red sin ella
DEFAULT_LIMIT = "100/minute"

# Topes que no van por red
LOGIN_ATTEMPTS_PER_EMAIL_LIMIT = "5/minute"
FAILED_LOGINS_LIMIT = "30/minute"  # por red, solo intentos fallidos
EMAIL_SENDING_PER_EMAIL_LIMIT = "3/hour"


def _clave_de_red(ip: str) -> str:
    """
    El contador de una IP: la IPv4 tal cual, y una IPv6 por su /64.

    Cada conexión IPv6 recibe un /64 entero: contar por dirección dejaría a quien
    llama estrenar contador en cada petición.
    """
    direccion = ipaddress.ip_address(ip)
    if isinstance(direccion, ipaddress.IPv6Address):
        return str(ipaddress.IPv6Network(f"{direccion}/64", strict=False))
    return ip


def get_client_identifier(request: Request) -> str:
    """
    Identificador de red del cliente.

    En producción: la IP que da Cloudflare si la petición trae su secreto (BE #466,
    ADR-041); si no, la del peer, que es el proxy de Render: el contador
    compartido de siempre, nunca uno que elija quien llama.
    Fuera de producción: X-Test-Client-ID si existe (simula clientes distintos).
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        ip = cloudflare_client_ip(request)
        return _clave_de_red(ip) if ip else get_remote_address(request)

    # En testing/development, permitir simular diferentes clientes con un header especial
    test_client_id = request.headers.get("X-Test-Client-ID")
    if test_client_id:
        return test_client_id

    # Fallback: usar IP real
    return get_remote_address(request)


def get_rate_limit_key(request: Request) -> str:
    """
    Clave de las rutas con sesión: el usuario del access token, o la red si no hay
    uno válido.

    El token se verifica (firma, caducidad y tipo) con la misma función que
    get_current_user. Sin verificar, cualquiera podría rotar el `sub` en cada
    petición y tener un contador nuevo cada vez.
    """
    token = read_access_token(request)
    payload = verify_access_token(token) if token else None
    user_id = payload.get("sub") if payload else None
    if user_id:
        return f"{_USER_PREFIX}{user_id}"
    return get_client_identifier(request)


_USER_PREFIX = "user:"


def refresh_token_rate_limit_key(request: Request) -> str:
    """
    Clave del refresco: el usuario de la cookie de refresh, o la red si no es válida.

    Se refresca cuando el acceso ya caducó, así que la clave de las rutas con
    sesión caería en la red, que en producción sin la IP real es toda la app: un
    torneo grande se quedaría sin poder refrescar (BE #467). El refresh se
    verifica entero (firma, caducidad y tipo): uno inventado no elige contador.
    """
    token = request.cookies.get(get_refresh_cookie_name())
    payload = verify_refresh_token(token) if token else None
    user_id = payload.get("sub") if payload else None
    if user_id:
        return f"{_USER_PREFIX}{user_id}"
    return get_client_identifier(request)


def get_hole_sample_rate_limit_key(request: Request) -> str:
    """
    Clave de mandar muestras de hoyo (BE #532): por usuario, como las demás rutas
    con sesión, pero sin su id.

    slowapi escribe la clave en el log al pasar del límite, y las muestras son
    anónimas: en vez de `user:<uuid>` va un HMAC-SHA256 del id con el secreto de
    la app, recortado. Sigue siendo uno por usuario y no se puede revertir sin el
    secreto. Sin sesión válida, la de red, como las demás.
    """
    key = get_rate_limit_key(request)
    if not key.startswith(_USER_PREFIX):
        return key
    user_id = key[len(_USER_PREFIX) :]
    digest = hmac.new(settings.SECRET_KEY.encode(), user_id.encode(), hashlib.sha256)
    return f"sample:{digest.hexdigest()[:32]}"


def email_rate_limit_key(email: str) -> str:
    """
    Clave de un email: normalizado como lo normaliza el dominio, y en hash.

    El hash evita guardar emails en claro en el almacenamiento de los contadores.
    """
    try:
        normalized = Email(email).value
    except InvalidEmailError:
        normalized = email.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _exceeded(limit_value: str) -> RateLimitExceeded:
    """La misma excepción, y por tanto la misma respuesta 429, que lanza slowapi."""
    return RateLimitExceeded(
        Limit(
            parse(limit_value),
            key_func=get_client_identifier,
            scope=None,
            per_method=False,
            methods=None,
            error_message=None,
            exempt_when=None,
            cost=1,
            override_defaults=True,
        )
    )


def count_or_refuse(limit_value: str, scope: str, identifier: str) -> None:
    """
    Cuenta una petición contra un límite que no es el de la ruta, y la rechaza con
    429 si lo supera.

    Para los límites que slowapi no puede expresar con un decorador, porque su
    clave sale del cuerpo de la petición (el email).

    Requiere que la ruta lleve también un @limiter.limit: el manejador del 429 lee
    lo que ese decorador deja en request.state.
    """
    if not limiter.enabled:  # apagado como los decoradores (limiter.enabled)
        return
    if not limiter.limiter.hit(parse(limit_value), scope, identifier):
        raise _exceeded(limit_value)


def refuse_if_failed_logins_exhausted(request: Request) -> None:
    """Rechaza el login con 429 si su red ha agotado el tope de fallos."""
    if not limiter.enabled:
        return
    if not limiter.limiter.test(
        parse(FAILED_LOGINS_LIMIT), "login-failures", get_client_identifier(request)
    ):
        raise _exceeded(FAILED_LOGINS_LIMIT)


def record_failed_login(request: Request) -> None:
    """Apunta un login fallido a su red, exista o no el email."""
    if not limiter.enabled:
        return
    limiter.limiter.hit(
        parse(FAILED_LOGINS_LIMIT), "login-failures", get_client_identifier(request)
    )


# Crear instancia global del limiter
# - key_func: el usuario en las rutas con sesión; las anónimas declaran
#   key_func=get_client_identifier (lo exige tests/unit/config/test_rate_limit_routes.py)
# - Sin default_limits: slowapi solo los aplica desde su middleware, que con
#   FastAPI 0.162 no encuentra las rutas de los routers. El límite por defecto es
#   la dependencia global `apply_default_rate_limit` (BE #467)
# NOTE: headers_enabled=False porque causa conflictos con endpoints que retornan DTOs
#       Los headers X-RateLimit-* solo aparecen cuando se excede el límite (HTTP 429)
limiter = Limiter(key_func=get_rate_limit_key)


# Exentas del límite por defecto (5 nov 2026): /health y la raíz las llama Render
# directo al origen; la documentación; y datos estáticos que se piden en ráfaga
# (los avatares predefinidos, con sus imágenes, y los países)
EXEMPT_FROM_DEFAULT_LIMIT = frozenset(
    {
        "main.root",
        "main.health",
        "main.get_documentation",
        "main.get_redoc_documentation",
        "src.modules.user.infrastructure.api.v1.avatar_routes.list_avatar_presets",
        "src.modules.user.infrastructure.api.v1.avatar_routes.get_avatar_preset_image",
        "src.shared.infrastructure.api.v1.country_routes.list_countries",
        "src.shared.infrastructure.api.v1.country_routes.list_adjacent_countries",
    }
)


def apply_default_rate_limit(request: Request) -> None:
    """
    El límite por defecto de toda ruta sin `@limiter.limit` propio (BE #467).

    Va como dependencia global de la app. Cuenta con la clave de siempre (el
    usuario con sesión, la red sin ella) y responde con el mismo 429 que slowapi.
    Una ruta con límite propio cuenta solo el suyo; las exentas, ninguno.
    """
    if not limiter.enabled:
        return
    endpoint = request.scope.get("endpoint")
    if endpoint is None:
        return
    nombre = f"{endpoint.__module__}.{endpoint.__name__}"
    if (
        nombre in EXEMPT_FROM_DEFAULT_LIMIT
        or nombre in limiter._route_limits
        or nombre in limiter._dynamic_route_limits
    ):
        return
    limite = parse(DEFAULT_LIMIT)
    clave = get_rate_limit_key(request)
    if not limiter.limiter.hit(limite, "default", clave):
        excedido = _exceeded(DEFAULT_LIMIT)
        # El manejador de slowapi lee el límite que saltó de aquí
        request.state.view_rate_limit = (limite, [clave, "default"])
        raise excedido


def limite_de_lo_publico(key: str) -> str:
    """
    El límite de lo que también ve un visitante (la clasificación por enlace,
    release social 3). Con sesión, el de siempre, por usuario. Sin ella, todos los
    visitantes comparten el contador de red en producción (ADR-038): con margen,
    hasta que cuente la IP real (BE #466). Decidido el 28 oct 2026.
    """
    return "30/minute" if key.startswith(_USER_PREFIX) else "600/minute"
