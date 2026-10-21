"""
La guarda de los Términos (B6) y su lista de rutas exentas.

Quien tiene sesión pero no tiene aceptada la versión vigente recibe un 403
`TERMS_NOT_ACCEPTED` en toda ruta con sesión, salvo las pocas que necesita para
ver quién es, aceptar, salir y gestionar sus dispositivos. La guarda vive en
`get_current_user`, así que una ruta nueva queda protegida sin hacer nada; lo
que hay que mantener es la lista de exentas, y estos tests la fijan.

La decisión se toma con API pública: el método y la ruta ASGI de la petición
(`request.scope["path"]`, la misma con la que casa el router; no
`request.url.path`, que se corta en un `?` o `#` codificados) contra las
plantillas completas de las exentas.
"""

import json
import logging
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

USUARIO = "3f2b8c1e-9d4a-4e7b-8a2f-1c5d6e7f8a9b"

DISPOSITIVO = "7c9e6679-7425-40de-944b-e07fc1f90ae7"

EXENTAS = {
    ("GET", "/api/v1/auth/current-user"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/users/me/accept-terms"),
    ("GET", "/api/v1/users/me/devices"),
    ("DELETE", "/api/v1/users/me/devices/{device_id}"),
}

# Cada exenta con una petición concreta que le corresponde
CONCRETAS = [
    ("GET", "/api/v1/auth/current-user"),
    ("POST", "/api/v1/auth/logout"),
    ("POST", "/api/v1/users/me/accept-terms"),
    ("GET", "/api/v1/users/me/devices"),
    ("DELETE", f"/api/v1/users/me/devices/{DISPOSITIVO}"),
]


def _request(method: str, path: str, root_path: str = "") -> Request:
    """Una petición con esa ruta, como la recibe la app (sin root_path en este montaje)."""
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "root_path": root_path,
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )


def _usuario(aceptado: bool) -> SimpleNamespace:
    return SimpleNamespace(id=USUARIO, terms_accepted=aceptado)


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
        Given: Las rutas de la app que exigen sesión, con su plantilla completa
        When: Se busca cada exenta entre ellas
        Then: Están todas: una exenta que ya no existe (o se renombró) no exime nada
        """
        assert _rutas_con_sesion() >= EXENTAS

    def test_there_are_session_routes_that_are_not_exempt(self):
        """
        Given: Las rutas con sesión
        When: Se quitan las exentas
        Then: Quedan muchas, todas tras la guarda
        """
        assert len(_rutas_con_sesion() - EXENTAS) > 50

    def test_no_other_session_route_matches_an_exemption(self):
        """
        Given: Cada ruta con sesión no exenta, con sus parámetros rellenos
        When: Se pregunta si está exenta
        Then: Ninguna lo está: ningún patrón de exención alcanza a otra ruta
        """
        colan = [
            (method, path)
            for method, path in _rutas_con_sesion() - EXENTAS
            if is_exempt_from_terms(
                method, path.replace("{", "").replace("}", "").replace(":path", "")
            )
        ]

        assert colan == []


class TestEsExenta:
    @pytest.mark.parametrize(("method", "path"), CONCRETAS)
    def test_exempt_request_is_exempt(self, method, path):
        """
        Given: Una petición concreta a una ruta exenta, con su método
        When: Se pregunta
        Then: Está exenta
        """
        assert is_exempt_from_terms(method, path) is True

    @pytest.mark.parametrize(("method", "path"), CONCRETAS)
    def test_trailing_slash_is_normalized(self, method, path):
        """
        Given: La misma petición con una barra final
        When: Se pregunta
        Then: Sigue exenta (se normaliza la ruta)
        """
        assert is_exempt_from_terms(method, path + "/") is True

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("POST", "/api/v1/auth/current-user"),
            ("GET", "/api/v1/users/me/accept-terms"),
            ("GET", "/api/v1/auth/logout"),
            ("DELETE", "/api/v1/users/me/devices"),
            ("GET", f"/api/v1/users/me/devices/{DISPOSITIVO}"),
            ("POST", f"/api/v1/users/me/devices/{DISPOSITIVO}"),
            ("DELETE", f"/api/v1/users/me/devices/{DISPOSITIVO}/extra"),
            ("DELETE", "/api/v1/users/me/devices/"),
            ("DELETE", "/api/v1/users/me/devicesX/abc"),
            ("DELETE", f"/x/api/v1/users/me/devices/{DISPOSITIVO}"),
            ("GET", "/api/v1/users/me/devices/../stats"),
            ("PATCH", "/api/v1/users/profile"),
            ("GET", "/api/v1/users/me/stats"),
            ("DELETE", "/api/v1/users/me/avatar"),
            ("GET", "/api/v1/auth/current-user-x"),
            ("GET", "/"),
        ],
    )
    def test_other_route_or_method_is_not_exempt(self, method, path):
        """
        Given: Otra ruta, la misma con otro método, o una que solo empieza igual
        When: Se pregunta
        Then: No está exenta: el patrón va anclado a un único segmento
        """
        assert is_exempt_from_terms(method, path) is False

    def test_method_is_case_insensitive(self):
        """
        Given: El método en minúsculas
        When: Se pregunta
        Then: Cuenta igual
        """
        assert is_exempt_from_terms("get", "/api/v1/auth/current-user") is True


class TestGuarda:
    def test_user_without_acceptance_is_refused_on_protected_route(self):
        """
        Given: Un usuario sin la versión vigente aceptada
        When: Llama a una ruta con sesión no exenta
        Then: TermsNotAcceptedError
        """
        with pytest.raises(TermsNotAcceptedError):
            require_current_terms(_request("GET", "/api/v1/users/me/stats"), _usuario(False))

    @pytest.mark.parametrize(("method", "path"), CONCRETAS)
    def test_user_without_acceptance_passes_on_exempt_route(self, method, path):
        """
        Given: Un usuario sin la versión vigente aceptada
        When: Llama a una ruta exenta con su método
        Then: Pasa
        """
        require_current_terms(_request(method, path), _usuario(False))

    @pytest.mark.parametrize(("method", "path"), CONCRETAS)
    def test_user_without_acceptance_is_refused_with_another_method(self, method, path):
        """
        Given: Un usuario sin la versión vigente aceptada
        When: Llama a la ruta de una exenta con otro método
        Then: Se le rechaza
        """
        otro = "PUT"
        with pytest.raises(TermsNotAcceptedError):
            require_current_terms(_request(otro, path), _usuario(False))

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            # Lo que llega en scope["path"] para .../current-user%3Fx: decodificado
            ("GET", "/api/v1/auth/current-user?x"),
            ("GET", "/api/v1/auth/current-user#x"),
            ("GET", "/api/v1/users/me/devices#x"),
            ("GET", "/api/v1/users/me/devices?x"),
            ("POST", "/api/v1/users/me/accept-terms?/../../stats"),
            ("POST", "/api/v1/auth/logout#/x"),
        ],
    )
    def test_encoded_question_mark_or_hash_does_not_exempt(self, method, path):
        """
        Given: Una petición cuya ruta lleva un %3F o %23 codificado (que ASGI
            entrega decodificado en scope["path"])
        When: Pasa por la guarda un usuario sin los Términos aceptados
        Then: Se le rechaza: la decisión se toma con la misma ruta con la que
            casa el router, no con la que Starlette rehace cortando en ? o #
        """
        with pytest.raises(TermsNotAcceptedError):
            require_current_terms(_request(method, path), _usuario(False))

    def test_user_with_acceptance_passes_everywhere(self):
        """
        Given: Un usuario con la versión vigente aceptada
        When: Llama a una ruta con sesión
        Then: Pasa
        """
        require_current_terms(_request("PATCH", "/api/v1/users/profile"), _usuario(True))


class TestRegistroDelBloqueo:
    """
    Cada bloqueo deja una línea WARNING (quién y dónde) en los logs de Render.

    WARNING y no INFO: la app no configura el root (queda en WARNING sin
    handlers), así que un INFO de `src.*` no saldría; y el LoggingIntegration
    de Sentry solo crea eventos desde ERROR (un WARNING es solo breadcrumb).
    """

    def _registros(self, caplog) -> list[logging.LogRecord]:
        return [r for r in caplog.records if r.name == "src.config.terms_guard"]

    def test_block_is_logged_with_user_method_and_path(self, caplog):
        """
        Given: Un usuario sin la versión vigente aceptada
        When: La guarda le rechaza una ruta (con query string)
        Then: Una línea WARNING con su id, el método y la ruta, sin la query
        """
        caplog.set_level(logging.INFO, logger="src.config.terms_guard")
        peticion = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/v1/users/me/stats",
                "root_path": "",
                "headers": [],
                "query_string": b"email=secreto@example.com",
                "scheme": "http",
                "server": ("testserver", 80),
            }
        )

        with pytest.raises(TermsNotAcceptedError):
            require_current_terms(peticion, _usuario(False))

        registros = self._registros(caplog)
        assert len(registros) == 1
        registro = registros[0]
        assert registro.levelno == logging.WARNING
        mensaje = registro.getMessage()
        assert USUARIO in mensaje
        assert "GET /api/v1/users/me/stats" in mensaje
        assert "TERMS_NOT_ACCEPTED" in mensaje
        assert "secreto" not in mensaje
        assert "?" not in mensaje

    @pytest.mark.parametrize(("method", "path"), CONCRETAS)
    def test_exempt_route_is_not_logged(self, caplog, method, path):
        """
        Given: Un usuario sin la versión vigente aceptada
        When: Llama a una ruta exenta
        Then: No se registra nada
        """
        caplog.set_level(logging.DEBUG, logger="src.config.terms_guard")
        require_current_terms(_request(method, path), _usuario(False))
        assert self._registros(caplog) == []

    def test_accepted_user_is_not_logged(self, caplog):
        """
        Given: Un usuario con la versión vigente aceptada
        When: Llama a una ruta con sesión
        Then: No se registra nada
        """
        caplog.set_level(logging.DEBUG, logger="src.config.terms_guard")
        require_current_terms(_request("GET", "/api/v1/users/me/stats"), _usuario(True))
        assert self._registros(caplog) == []


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
        # Las PWA anteriores a la 2.49 no conocen /accept-terms y pintan el
        # `detail` tal cual: tiene que decirles qué hacer
        assert cuerpo["detail"] == (
            "Tienes que aceptar los nuevos Términos de uso. "
            "Cierra la app por completo y vuelve a abrirla para aceptarlos."
        )
        assert set(cuerpo) == {"detail", "error_code"}

    def test_handler_is_registered_in_the_app(self):
        """
        Given: La app montada
        When: Se mira su tabla de errores
        Then: TermsNotAcceptedError tiene su traducción (sin ella saldría un 500)
        """
        assert app.exception_handlers.get(TermsNotAcceptedError) is terms_not_accepted_handler


class TestDocumentacion:
    def test_accept_terms_openapi_lists_every_exempt_route(self):
        """
        Given: La documentación OpenAPI de accept-terms
        When: Se lee su descripción
        Then: Cita todas las rutas exentas, sacadas de TERMS_EXEMPT_ROUTES
            (si se añade una, la documentación la incluye sola)
        """
        descripcion = app.openapi()["paths"]["/api/v1/users/me/accept-terms"]["post"]["description"]

        for method, path in TERMS_EXEMPT_ROUTES:
            assert f"{method} {path}" in descripcion
