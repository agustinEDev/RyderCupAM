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

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.routing import get_route_path

from src.modules.user.application.dto.user_dto import UserResponseDTO

TERMS_NOT_ACCEPTED = "TERMS_NOT_ACCEPTED"

# (método, ruta completa) exentos. Una lista explícita y cerrada: añadir una
# es una decisión, y tests/unit/config/test_terms_guard.py la fija. Se compara
# con la ruta CONCRETA de la petición (no con la plantilla: la de un router
# incluido llega sin su prefijo), así que una exenta no puede llevar parámetros
TERMS_EXEMPT_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        # Quién soy y qué versión se me pide: pinta la pantalla de aceptación
        ("GET", "/api/v1/auth/current-user"),
        # Aceptar
        ("POST", "/api/v1/users/me/accept-terms"),
        # Salir sin aceptar
        ("POST", "/api/v1/auth/logout"),
    }
)


class TermsNotAcceptedError(Exception):
    """El usuario autenticado no tiene aceptada la versión vigente de los Términos."""

    error_code = TERMS_NOT_ACCEPTED

    def __init__(self, message: str = "Debes aceptar los Términos de uso vigentes para continuar."):
        super().__init__(message)


def is_exempt_from_terms(method: str, route_path: str | None) -> bool:
    """
    Si esa ruta se puede usar sin tener aceptados los Términos.

    Args:
        method: Método HTTP de la petición
        route_path: Ruta completa de la petición (p. ej. `/api/v1/auth/current-user`),
            o None si FastAPI no resolvió ninguna ruta, que nunca está exenta

    Returns:
        True solo si el par (método, ruta) está en la lista de exentas
    """
    if route_path is None:
        return False
    return (method.upper(), route_path) in TERMS_EXEMPT_ROUTES


def require_current_terms(request: Request, user: UserResponseDTO) -> None:
    """
    Deja pasar si el usuario tiene aceptada la versión vigente, o si la ruta está exenta.

    Args:
        request: La petición, con la ruta ya resuelta por FastAPI
        user: El usuario autenticado

    Raises:
        TermsNotAcceptedError: Si no los tiene aceptados y la ruta no está exenta
    """
    if user.terms_accepted:
        return
    # La ruta con la que FastAPI casó la petición (sin root_path), solo si
    # resolvió una
    route_path = get_route_path(request.scope) if request.scope.get("route") else None
    if is_exempt_from_terms(request.method, route_path):
        return
    raise TermsNotAcceptedError()


async def terms_not_accepted_handler(_request: Request, exc: Exception) -> JSONResponse:
    """403 con el motivo y su código, como los demás errores con código."""
    error_code = getattr(exc, "error_code", TERMS_NOT_ACCEPTED)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc), "error_code": error_code},
    )
