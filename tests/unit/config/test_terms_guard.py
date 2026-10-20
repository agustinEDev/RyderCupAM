"""
La guarda de los Términos (B6) y su lista de rutas exentas.

Quien tiene sesión pero no tiene aceptada la versión vigente recibe un 403
`TERMS_NOT_ACCEPTED` en toda ruta con sesión, salvo las pocas que necesita para
ver quién es, aceptar o salir. La guarda vive en `get_current_user`, así que
una ruta nueva queda protegida sin hacer nada; lo que hay que mantener es la
lista de exentas, y estos tests la fijan.
"""

import json
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi import Request
from fastapi.routing import APIRoute

from main import app
from src.config.dependencies import get_current_user
from src.config.terms_guard import (
    TERMS_EXEMPT_ROUTES,
    TermsNotAcceptedError,
    is_exempt_from_terms,
    require_current_terms,
    terms_not_accepted_handler,
)

EXENTAS = {
    ("GET", "/api/v1/auth/current-user"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/users/me/accept-terms"),
}


def _request(method: str, path: str | None) -> Request:
    """Una petición ya resuelta por FastAPI; con path None, sin ruta resuelta."""
    scope = {"type": "http", "method": method, "path": path or "/", "headers": []}
    if path is not None:
        # Como la pone FastAPI en un router incluido: la plantilla SIN el prefijo
        scope["route"] = SimpleNamespace(path=path.rsplit("/", 1)[-1])
    return Request(scope)


def _usuario(aceptado: bool) -> SimpleNamespace:
    return SimpleNamespace(terms_accepted=aceptado)


def _routes(routes, prefix: str = "") -> Iterator[tuple[str, APIRoute]]:
    """Cada ruta de la app con su ruta completa (los routers incluidos guardan aparte su prefijo)."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
        elif hasattr(route, "original_router"):
            yield from _routes(route.original_router.routes, prefix + route.include_context.prefix)
        elif hasattr(route, "routes"):
            yield from _routes(route.routes, prefix)


def _dependencies(dependant) -> Iterator:
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _dependencies(dependency)


def _rutas_con_sesion() -> set[tuple[str, str]]:
    return {
        (method, path)
        for path, route in _routes(app.routes)
        if get_current_user in set(_dependencies(route.dependant))
        for method in route.methods
    }


class TestListaDeExentas:
    def test_exempt_routes_are_exactly_these(self):
        """
        Given: La lista de rutas exentas
        When: Se compara con la aprobada
        Then: Es exactamente esa: añadir o quitar una es una decisión
        """
        assert set(TERMS_EXEMPT_ROUTES) == EXENTAS

    def test_every_exempt_route_exists_and_requires_session(self):
        """
        Given: Las rutas de la app que exigen sesión
        When: Se busca cada exenta entre ellas
        Then: Están todas: una exenta que ya no existe (o se renombró) no exime nada
        """
        con_sesion = _rutas_con_sesion()

        assert con_sesion >= EXENTAS

    def test_there_are_session_routes_that_are_not_exempt(self):
        """
        Given: Las rutas con sesión
        When: Se quitan las exentas
        Then: Quedan muchas, todas tras la guarda
        """
        assert len(_rutas_con_sesion() - EXENTAS) > 50


class TestEsExenta:
    @pytest.mark.parametrize(("method", "path"), sorted(EXENTAS))
    def test_exempt_route_is_exempt(self, method, path):
        """
        Given: Una ruta exenta con su método
        When: Se pregunta
        Then: Está exenta
        """
        assert is_exempt_from_terms(method, path) is True

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("POST", "/api/v1/auth/current-user"),
            ("GET", "/api/v1/users/me/accept-terms"),
            ("GET", "/api/v1/auth/logout"),
            ("PATCH", "/api/v1/users/profile"),
            ("GET", "/api/v1/users/me/stats"),
            ("GET", "/api/v1/auth/current-user/"),
            ("GET", None),
        ],
    )
    def test_other_route_or_method_is_not_exempt(self, method, path):
        """
        Given: Otra ruta, la misma con otro método, o sin ruta resuelta
        When: Se pregunta
        Then: No está exenta (ante la duda, se protege)
        """
        assert is_exempt_from_terms(method, path) is False


class TestGuarda:
    def test_user_without_acceptance_is_refused_on_protected_route(self):
        """
        Given: Un usuario sin la versión vigente aceptada
        When: Llama a una ruta con sesión no exenta
        Then: TermsNotAcceptedError
        """
        with pytest.raises(TermsNotAcceptedError):
            require_current_terms(_request("GET", "/api/v1/users/me/stats"), _usuario(False))

    @pytest.mark.parametrize(("method", "path"), sorted(EXENTAS))
    def test_user_without_acceptance_passes_on_exempt_route(self, method, path):
        """
        Given: Un usuario sin la versión vigente aceptada
        When: Llama a una ruta exenta
        Then: Pasa
        """
        require_current_terms(_request(method, path), _usuario(False))

    def test_user_with_acceptance_passes_everywhere(self):
        """
        Given: Un usuario con la versión vigente aceptada
        When: Llama a una ruta con sesión
        Then: Pasa
        """
        require_current_terms(_request("PATCH", "/api/v1/users/profile"), _usuario(True))

    def test_user_without_acceptance_and_no_route_is_refused(self):
        """
        Given: Una petición sin ruta resuelta
        When: Pasa por la guarda
        Then: Se rechaza
        """
        with pytest.raises(TermsNotAcceptedError):
            require_current_terms(_request("GET", None), _usuario(False))


class TestRespuesta:
    @pytest.mark.asyncio
    async def test_handler_returns_403_with_error_code(self):
        """
        Given: La guarda ha rechazado una petición
        When: La traduce la API
        Then: 403 con `detail` y `error_code` TERMS_NOT_ACCEPTED en la raíz
        """
        respuesta = await terms_not_accepted_handler(
            _request("GET", "/api/v1/users/me/stats"), TermsNotAcceptedError()
        )

        assert respuesta.status_code == 403
        cuerpo = json.loads(respuesta.body)
        assert cuerpo["error_code"] == "TERMS_NOT_ACCEPTED"
        assert isinstance(cuerpo["detail"], str) and cuerpo["detail"]

    def test_handler_is_registered_in_the_app(self):
        """
        Given: La app montada
        When: Se mira su tabla de errores
        Then: TermsNotAcceptedError tiene su traducción (sin ella saldría un 500)
        """
        assert app.exception_handlers.get(TermsNotAcceptedError) is terms_not_accepted_handler
