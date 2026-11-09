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
- **Toda ruta con sesión sin límite propio**: DEFAULT_LIMIT por usuario y por ruta,
  como dependencia global de la app (BE #467), salvo las de EXEMPT_FROM_DEFAULT_LIMIT.
  Sin usuario verificado no cuenta: una ruta anónima nueva necesita su propio
  @limiter.limit (lo vigila test_every_route_a_visitor_can_reach_has_a_limit).
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

from src.config.arranque_seguro import en_desarrollo_declarado, testing_activado
from src.config.settings import settings
from src.modules.user.domain.value_objects.email import Email, InvalidEmailError
from src.shared.infrastructure.http.http_context_validator import cloudflare_client_ip
from src.shared.infrastructure.security.cookie_handler import (
    get_refresh_cookie_name,
    read_access_token,
)
from src.shared.infrastructure.security.jwt_handler import (
    expired_refresh_subject,
    verify_access_token,
    verify_refresh_token,
)

# Topes de las rutas anónimas: por red, que en producción es toda la app
# Techo de intentos por red, de cualquier correo: protege la CPU (cada login que pasa
# el freno cuesta un bcrypt). 120 desde BE #732: un atacante en la misma red que el
# dueño (la wifi del club) le deja en 429 mientras dure; al doble, le cuesta el doble.
# La fuerza bruta la acota el freno del login (5/min por correo, 30 fallos/min por red)
LOGIN_ATTEMPTS_LIMIT = "120/minute"
GOOGLE_LOGIN_LIMIT = "30/minute"
REGISTER_LIMIT = "30/hour"
EMAIL_SENDING_LIMIT = "30/hour"  # forgot-password y resend-verification
RESET_PASSWORD_LIMIT = "20/hour"  # nosec B105 - a rate limit, not a password
VALIDATE_RESET_TOKEN_LIMIT = "30/hour"  # nosec B105 - a rate limit, not a token
# Por red y DÍA (auditoría OWASP, 6 nov 2026; antes 10 por hora): una red sola llena
# como mucho la mitad del tope de 20 al día de la app. 10 y no menos: como los demás,
# dimensionado para un club entero, o para todos si falla la IP real (una sola red)
CONTACT_LIMIT = "10/day"

# Credenciales EQUIVOCADAS de la documentación (/docs, /redoc y /openapi.json), por
# red (F-11 y /code-review, 9 nov 2026): probar contraseñas deja de ser gratis. Las
# buenas ni cuentan ni se frenan: sin la IP real la red es toda la app, y cualquiera
# dejaría al administrador sin documentación
DOCS_LIMIT = "20/minute"

VERIFY_EMAIL_LIMIT = "60/hour"  # el doble que el registro: cuenta los enlaces reintentados
REFRESH_TOKEN_LIMIT = "30/minute"  # nosec B105 - a rate limit, not a token

# El de toda ruta sin límite propio (BE #467): por usuario y por ruta. Sin usuario
# verificado no cuenta: esas rutas exigen sesión y dan su 401
DEFAULT_LIMIT = "100/minute"

# Rutas sin límite propio con un tope por defecto más alto: anotar un hoyo de
# partida rápida. Al volver la cobertura la cola manda 4 x 18 golpes seguidos
DEFAULT_LIMIT_OVERRIDES = {
    "src.modules.quick_match.infrastructure.api.v1.quick_match_routes.submit_hole_score": "300/minute",
    "src.modules.quick_match.infrastructure.api.v1.quick_match_routes.submit_proxy_hole_score": (
        "300/minute"
    ),
}

# Topes que no van por red
# Por correo + origen (la red, o el dispositivo fiable), no por correo solo: cinco
# intentos ajenos dejaban al dueño en 429 (BE #732). Lo cuenta el freno del login
LOGIN_ATTEMPTS_PER_EMAIL_LIMIT = "5/minute"
FAILED_LOGINS_LIMIT = "30/minute"  # por red, solo intentos fallidos
EMAIL_SENDING_PER_EMAIL_LIMIT = "3/hour"
# PATCH /users/security, por usuario (BE #753): cada petición prueba una contraseña, y
# pedir un correo nuevo manda dos correos, uno a cualquier dirección, del cupo diario
SECURITY_CHANGES_LIMIT = "10/hour"
NEW_EMAIL_REQUESTS_LIMIT = "3/hour"


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
    En desarrollo y en los tests: X-Test-Client-ID si existe (simula clientes
    distintos). Sin ENVIRONMENT, o con un valor desconocido, como en producción.
    """
    if not _admite_el_cliente_de_prueba():
        ip = cloudflare_client_ip(request)
        return _clave_de_red(ip) if ip else get_remote_address(request)

    # En los tests y en desarrollo, simular clientes distintos con una cabecera
    test_client_id = request.headers.get("X-Test-Client-ID")
    if test_client_id:
        return test_client_id

    # Fallback: usar IP real
    return get_remote_address(request)


def _admite_el_cliente_de_prueba() -> bool:
    """
    Si vale X-Test-Client-ID: solo en la suite de tests, con TESTING=true Y
    ENVIRONMENT=development.

    Antes, sin ENVIRONMENT se tomaba por desarrollo: una producción mal configurada
    dejaba a quien llama elegir su red, y con ella el freno del login (auditoría
    OWASP de BE #732, A05). Y bastaba TESTING o development: ahora hacen falta los
    dos (F-12, 9 nov 2026). Un valor desconocido cuenta como producción.
    """
    return testing_activado(os.environ) and en_desarrollo_declarado(os.environ)


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


def _clave_de_usuario(user_id: str) -> str:
    """El contador de un usuario: un identificador interno, nunca se devuelve a nadie."""
    return _USER_PREFIX + user_id


def refresh_token_rate_limit_key(request: Request) -> str:
    """
    Clave del refresco: el usuario y el token de la cookie de refresh, o la red.

    Se refresca cuando el acceso ya caducó, así que la clave de las rutas con
    sesión caería en la red, que en producción sin la IP real es toda la app: un
    torneo grande se quedaría sin poder refrescar (BE #467). El refresh se
    verifica entero (firma, caducidad y tipo): uno inventado no elige contador.
    """
    token = request.cookies.get(get_refresh_cookie_name())
    payload = verify_refresh_token(token) if token else None
    user_id = payload.get("sub") if payload else None
    if token and not user_id:
        # El caducado con la firma buena también cuenta: cuesta consultas a la BD (se
        # mira si el navegador tiene una sesión nueva, BE #734, /code-review)
        user_id = expired_refresh_subject(token)
    if token and user_id:
        # Por usuario y por token: con un refresh suyo ya revocado, nadie agota el
        # contador de sus otros dispositivos (auditoría OWASP, 5 nov 2026). El token,
        # en hash: la clave sale en el log de slowapi al pasar del límite
        huella = hashlib.sha256(token.encode()).hexdigest()[:16]
        return _clave_de_usuario(f"{user_id}:{huella}")
    return get_client_identifier(request)


def skip_refresh_limit_without_valid_cookie(request: Request) -> bool:
    """
    El refresco sin cookie de refresh válida no cuenta: va a dar su 401.

    Lo prueba cada visitante anónimo (la sonda de sesión), y por red, que sin la IP
    real es toda la app, cualquiera podría agotar el contador de todos y dejar en
    429 a quien tenga la cookie caducada (revisor y /code-review, 5 nov 2026).
    """
    return not refresh_token_rate_limit_key(request).startswith(_USER_PREFIX)


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


def cabe(limit_value: str, scope: str, identifier: str) -> bool:
    """
    Cuenta una petición contra un límite y dice si cabía, sin lanzar nada.

    Para las rutas que responden su propio 429 con un código traducible; las demás
    usan count_or_refuse. Una petición que no cabe también se cuenta (limits suma antes
    de comparar), lo que no alarga la ventana fija.
    """
    if not limiter.enabled:
        return True
    return bool(limiter.limiter.hit(parse(limit_value), scope, identifier))


def clave_de_usuario(user_id: str) -> str:
    """El contador de un usuario para los límites que se cuentan a mano."""
    return _clave_de_usuario(user_id)


def too_many_login_attempts() -> RateLimitExceeded:
    """El 429 del freno del login (BE #732): el mismo que cualquier otro límite."""
    return _exceeded(LOGIN_ATTEMPTS_PER_EMAIL_LIMIT)


def too_many_failed_logins_from_network() -> RateLimitExceeded:
    """El 429 del techo de fallos de una red (#273): el mismo que cualquier límite."""
    return _exceeded(FAILED_LOGINS_LIMIT)


def failed_logins_exhausted(red: str) -> bool:
    """
    Si la red (la clave de get_client_identifier) agotó el techo de fallos del login.

    Lo pregunta el freno del login, y no la ruta, desde BE #732: un dispositivo
    fiable de la cuenta no lo sufre (en la wifi del club con un atacante dentro).
    """
    if not limiter.enabled:
        return False
    return not limiter.limiter.test(parse(FAILED_LOGINS_LIMIT), "login-failures", red)


def record_failed_login(red: str) -> None:
    """Apunta un login fallido a su red, exista o no el email."""
    if not limiter.enabled:
        return
    limiter.limiter.hit(parse(FAILED_LOGINS_LIMIT), "login-failures", red)


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
# directo al origen; la documentación, que lleva el suyo por red
# (limita_la_documentacion, F-11); y datos estáticos que se piden en ráfaga (los
# avatares predefinidos, con sus imágenes, y los países)
EXEMPT_FROM_DEFAULT_LIMIT = frozenset(
    {
        "main.root",
        "main.health",
        "main.get_documentation",
        "main.get_redoc_documentation",
        "main.get_openapi_schema",
        "src.modules.user.infrastructure.api.v1.avatar_routes.list_avatar_presets",
        "src.modules.user.infrastructure.api.v1.avatar_routes.get_avatar_preset_image",
        "src.shared.infrastructure.api.v1.country_routes.list_countries",
        "src.shared.infrastructure.api.v1.country_routes.list_adjacent_countries",
    }
)


async def apply_default_rate_limit(request: Request) -> None:
    """
    El límite por defecto de toda ruta sin `@limiter.limit` propio (BE #467).

    Va como dependencia global de la app y responde con el mismo 429 que slowapi.
    Una ruta con límite propio cuenta solo el suyo; las exentas, ninguno.

    - Cuenta **por usuario y por ruta**: un sondeo no deja sin servicio a las demás.
      Algunas rutas tienen un tope más alto (DEFAULT_LIMIT_OVERRIDES).
    - **Sin usuario verificado no cuenta.** Estas rutas exigen sesión y van a dar su
      401, que es lo que hace al front refrescar. Con la clave de red, que sin la IP
      real es toda la app, un acceso caducado recibía 429 y nunca refrescaba
      (revisor, 5 nov 2026). Es async: síncrona saltaría al pool de hilos cada vez.
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
    clave = get_rate_limit_key(request)
    if not clave.startswith(_USER_PREFIX):
        return
    valor = DEFAULT_LIMIT_OVERRIDES.get(nombre, DEFAULT_LIMIT)
    limite = parse(valor)
    # Como slowapi: (clave, ámbito), con su prefijo si lo hubiera. Sus cabeceras
    # X-RateLimit leen la ventana con estos mismos identificadores
    identificadores = [clave, nombre]
    if limiter._key_prefix:
        identificadores = [limiter._key_prefix, *identificadores]
    if not limiter.limiter.hit(limite, *identificadores):
        excedido = _exceeded(valor)
        # El manejador de slowapi lee el límite que saltó de aquí
        request.state.view_rate_limit = (limite, identificadores)
        raise excedido


def cuenta_un_fallo_de_la_documentacion(request: Request) -> None:
    """
    Cuenta unas credenciales equivocadas de la documentación (DOCS_LIMIT), por red, y
    pasado el límite responde con el mismo 429 que slowapi (F-11, /code-review).

    Solo se llama con credenciales equivocadas: las buenas ni cuentan ni se frenan.
    """
    if not limiter.enabled:
        return
    limite = parse(DOCS_LIMIT)
    identificadores = [get_client_identifier(request), "docs"]
    if limiter._key_prefix:
        identificadores = [limiter._key_prefix, *identificadores]
    if not limiter.limiter.hit(limite, *identificadores):
        # El manejador de slowapi lee el límite que saltó de aquí
        request.state.view_rate_limit = (limite, identificadores)
        raise _exceeded(DOCS_LIMIT)


def limite_de_lo_publico(key: str) -> str:
    """
    El límite de lo que también ve un visitante (la clasificación por enlace,
    release social 3). Con sesión, el de siempre, por usuario. Sin ella, todos los
    visitantes comparten el contador de red en producción (ADR-038): con margen,
    hasta que cuente la IP real (BE #466). Decidido el 28 oct 2026.
    """
    return "30/minute" if key.startswith(_USER_PREFIX) else "600/minute"
