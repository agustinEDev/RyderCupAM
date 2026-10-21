"""
La guarda de los Términos de uso (B6).

Quien tiene sesión pero no tiene aceptada la versión vigente de los Términos
(`terms_of_service.CURRENT_TERMS_VERSION`) no usa la aplicación: cualquier ruta
con sesión le responde 403 con `error_code: TERMS_NOT_ACCEPTED`, el mismo
formato que el resto de códigos que lee el frontend (`detail` + `error_code` en
la raíz). Cierra el hueco del alta con Google y de las llamadas directas a la
API, que no pasan por la casilla del formulario de registro.

La guarda se aplica en un solo sitio, `get_current_user`, así que toda ruta
con sesión (incluidas las que se añadan mañana) queda protegida sin tocarla.
Las rutas sin sesión no pasan por ahí y no se ven afectadas, y el refresco del
token tampoco (no usa `get_current_user`).

Las exentas son las imprescindibles para que el frontend sepa quién es y qué
versión se le pide, acepte y pueda cerrar sesión. Completar el perfil NO está
exento: el frontend acepta primero y luego guarda el perfil.
"""

import logging
import re

from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.modules.user.application.dto.user_dto import UserResponseDTO

logger = logging.getLogger(__name__)

TERMS_NOT_ACCEPTED = "TERMS_NOT_ACCEPTED"

# Lo que pintan tal cual las PWA anteriores a la 2.49, que no conocen
# /accept-terms: tiene que decir cómo llegar a la pantalla de aceptación. En los
# dos idiomas, porque esas versiones no lo traducen
TERMS_NOT_ACCEPTED_MESSAGE = (
    "Tienes que aceptar los nuevos Términos de uso. "
    "Cierra la app por completo y vuelve a abrirla para aceptarlos. / "
    "You must accept the new Terms of Use. "
    "Close the app completely and open it again to accept them."
)

# (método, plantilla COMPLETA de la ruta) exentos. Una lista explícita y
# cerrada: añadir una es una decisión, y tests/unit/config/test_terms_guard.py
# la fija y comprueba que cada una existe y que no alcanza a ninguna otra ruta
TERMS_EXEMPT_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        # Quién soy y qué versión se me pide: pinta la pantalla de aceptación
        ("GET", "/api/v1/auth/current-user"),
        # Aceptar
        ("POST", "/api/v1/users/me/accept-terms"),
        # Salir sin aceptar
        ("POST", "/api/v1/auth/logout"),
        # Ver y cerrar sus sesiones sin aceptar antes: quien sospecha que le
        # han robado una tiene que poder cerrarla ya (decisión de Agustín)
        ("GET", "/api/v1/users/me/devices"),
        ("DELETE", "/api/v1/users/me/devices/{device_id}"),
    }
)

# Un parámetro de ruta ocupa UN segmento, igual que en el router de FastAPI
# (el convertidor por defecto es `[^/]+`)
_PARAMETRO = re.compile(r"\{[^{}/]+\}")


def _patron(plantilla: str) -> re.Pattern[str]:
    """La plantilla como expresión regular anclada: cada parámetro, un segmento."""
    partes = _PARAMETRO.split(plantilla)
    return re.compile("[^/]+".join(re.escape(parte) for parte in partes))


_EXEMPT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (method, _patron(plantilla)) for method, plantilla in sorted(TERMS_EXEMPT_ROUTES)
)


class TermsNotAcceptedError(Exception):
    """El usuario autenticado no tiene aceptada la versión vigente de los Términos."""

    error_code = TERMS_NOT_ACCEPTED

    def __init__(self, message: str = TERMS_NOT_ACCEPTED_MESSAGE):
        super().__init__(message)


def _normalize(path: str) -> str:
    """Sin barras finales (la raíz se queda en "/")."""
    return path.rstrip("/") or "/"


def is_exempt_from_terms(method: str, path: str) -> bool:
    """
    Si esa petición se puede hacer sin tener aceptados los Términos.

    Args:
        method: Método HTTP de la petición
        path: Ruta concreta de la petición (p. ej. `/api/v1/users/me/devices/<id>`)

    Returns:
        True solo si el método coincide y la ruta, normalizada, encaja ENTERA
        con la plantilla de una exenta (fullmatch: nada de prefijos abiertos)
    """
    method = method.upper()
    path = _normalize(path)
    return any(
        method == exempt_method and pattern.fullmatch(path)
        for exempt_method, pattern in _EXEMPT_PATTERNS
    )


def require_current_terms(request: Request, user: UserResponseDTO) -> None:
    """
    Deja pasar si el usuario tiene aceptada la versión vigente, o si la ruta está exenta.

    Se decide con `request.method` y `request.scope["path"]`: la ruta de la
    especificación ASGI, ya decodificada, que es exactamente la cadena con la
    que el router de Starlette casa la petición (la app se sirve sin
    `root_path`: uvicorn arranca sin `--root-path`, ver entrypoint.sh; si algún
    día se montara bajo un prefijo, las plantillas de TERMS_EXEMPT_ROUTES
    tendrían que llevarlo). NO `request.url.path`: Starlette rehace la URL con
    la ruta decodificada y la corta en un `%3F` o `%23` codificado, así que
    `/api/v1/auth/current-user%3Fx` parecería current-user sin serlo.

    Args:
        request: La petición
        user: El usuario autenticado

    Raises:
        TermsNotAcceptedError: Si no los tiene aceptados y la ruta no está exenta
    """
    if user.terms_accepted:
        return
    path = request.scope["path"]
    if is_exempt_from_terms(request.method, path):
        return
    # Quién choca con la guarda y desde dónde, para verlo en Render. WARNING:
    # el root no está configurado y un INFO de `src.*` no saldría; Sentry solo
    # crea issues desde ERROR. Solo el id y la ruta ASGI (sin query string),
    # escapada: llega decodificada y un %0A falsearía líneas del log
    ruta_escapada = path.encode("unicode_escape").decode("ascii")
    logger.warning(
        "%s: user %s on %s %s", TERMS_NOT_ACCEPTED, user.id, request.method, ruta_escapada
    )
    raise TermsNotAcceptedError()


async def terms_not_accepted_handler(_request: Request, exc: Exception) -> JSONResponse:
    """403 con el motivo y su código, como los demás errores con código."""
    error_code = getattr(exc, "error_code", TERMS_NOT_ACCEPTED)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc), "error_code": error_code},
    )
