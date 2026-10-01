"""
Rate Limiting Configuration

Configuración centralizada de rate limiting para la API.

Quién cuenta en cada límite (RyderCupAM#273, ADR-038):

- **Rutas con sesión**: el usuario, sacado de un access token cuya firma se
  verifica. Es una identidad que pone el servidor: un token inventado no elige
  contador y cae en el de red.
- **Rutas anónimas**: la red (`get_client_identifier`), declarada en cada ruta. En
  producción es la IP del proxy de Render, o sea, un contador para toda la app: por
  eso sus topes están dimensionados para un club entero entrando a la vez.
- **Login, forgot-password y resend-verification**: además, por email, contado
  antes de saber si el email existe. Y el login, por red, solo cuenta los fallos:
  los aciertos de un club no lo cierran, y el credential stuffing, que casi solo
  falla, sí.

Ninguna clave sale de una cabecera que escriba el cliente (ADR-038).
"""

import hashlib
import os

from limits import parse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.wrappers import Limit
from starlette.requests import Request

from src.modules.user.domain.value_objects.email import Email, InvalidEmailError
from src.shared.infrastructure.security.cookie_handler import read_access_token
from src.shared.infrastructure.security.jwt_handler import verify_access_token

# Topes de las rutas anónimas: por red, que en producción es toda la app
LOGIN_ATTEMPTS_LIMIT = "60/minute"  # techo de intentos: cada login cuesta un bcrypt
GOOGLE_LOGIN_LIMIT = "30/minute"
REGISTER_LIMIT = "30/hour"
EMAIL_SENDING_LIMIT = "30/hour"  # forgot-password y resend-verification
RESET_PASSWORD_LIMIT = "20/hour"
VALIDATE_RESET_TOKEN_LIMIT = "30/hour"
CONTACT_LIMIT = "10/hour"

# Topes que no van por red
LOGIN_ATTEMPTS_PER_EMAIL_LIMIT = "5/minute"
FAILED_LOGINS_LIMIT = "30/minute"  # por red, solo intentos fallidos
EMAIL_SENDING_PER_EMAIL_LIMIT = "3/hour"


def get_client_identifier(request: Request) -> str:
    """
    Identificador de red del cliente.

    En testing/development: Usa el header X-Test-Client-ID si existe (permite simular diferentes clientes).
    En producción: Usa SOLO la IP real del cliente (ignora headers para evitar bypass).
    """
    # En producción, SIEMPRE usar IP real (ignorar headers por seguridad)
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        return get_remote_address(request)

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
        return f"user:{user_id}"
    return get_client_identifier(request)


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
# - default_limits: no se aplica a ninguna ruta, porque no hay SlowAPIMiddleware
# NOTE: headers_enabled=False porque causa conflictos con endpoints que retornan DTOs
#       Los headers X-RateLimit-* solo aparecen cuando se excede el límite (HTTP 429)
limiter = Limiter(key_func=get_rate_limit_key, default_limits=["100/minute"])
