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

import re

from fastapi import Request, status
from fastapi.responses import JSONResponse

from src.modules.user.application.dto.user_dto import UserResponseDTO

TERMS_NOT_ACCEPTED = "TERMS_NOT_ACCEPTED"

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

    def __init__(self, message: str = "Debes aceptar los Términos de uso vigentes para continuar."):
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

    Se decide con API pública de Starlette: `request.method` y
    `request.url.path`. Esa ruta es la completa de la petición, con el prefijo
    del router, y es la misma con la que el router la casó porque la app se
    sirve sin `root_path` (uvicorn arranca sin `--root-path`, ver
    entrypoint.sh): si algún día se montara bajo un prefijo, las plantillas de
    TERMS_EXEMPT_ROUTES tendrían que llevarlo.

    Args:
        request: La petición
        user: El usuario autenticado

    Raises:
        TermsNotAcceptedError: Si no los tiene aceptados y la ruta no está exenta
    """
    if user.terms_accepted:
        return
    if is_exempt_from_terms(request.method, request.url.path):
        return
    raise TermsNotAcceptedError()


async def terms_not_accepted_handler(_request: Request, exc: Exception) -> JSONResponse:
    """403 con el motivo y su código, como los demás errores con código."""
    error_code = getattr(exc, "error_code", TERMS_NOT_ACCEPTED)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc), "error_code": error_code},
    )
