"""
El límite por defecto, de verdad aplicado (BE #467).

`Limiter(default_limits=[...])` no se aplicaba a ninguna ruta: slowapi solo lo
mira desde su middleware, y con FastAPI 0.162 ese middleware no encuentra las
rutas de los routers incluidos. Ahora es una dependencia global de la app: toda
ruta sin `@limiter.limit` propio cuenta contra DEFAULT_LIMIT, con la clave de
siempre (el usuario con sesión, la red sin ella), salvo las exentas a propósito.
"""

import inspect
import time
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.config import rate_limit
from src.config.rate_limit import (
    EXEMPT_FROM_DEFAULT_LIMIT,
    apply_default_rate_limit,
    limite_del_refresco,
    limiter,
    refresh_token_rate_limit_key,
)
from src.config.settings import settings
from src.shared.infrastructure.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
)


def _app() -> FastAPI:
    """Una app mínima montada como la real: la dependencia global y el 429 de slowapi."""
    app = FastAPI(dependencies=[Depends(apply_default_rate_limit)])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/sin-limite")
    async def sin_limite_propio():
        """Una ruta sin límite propio."""
        return {"ok": True}

    @app.get("/con-limite")
    @limiter.limit("50/minute")
    async def con_limite_propio(request: Request):
        """Una ruta con su propio límite, más alto que el de por defecto del test."""
        return {"ok": True}

    @app.get("/otra-sin-limite")
    async def otra_sin_limite_propio():
        """Otra ruta sin límite propio."""
        return {"ok": True}

    @app.get("/exenta")
    async def exenta_del_test():
        """Una ruta que el test declara exenta."""
        return {"ok": True}

    return app


@pytest.fixture
def cliente(monkeypatch):
    """La app mínima con el límite por defecto a 3/minuto y los contadores a cero."""
    monkeypatch.setattr(rate_limit, "DEFAULT_LIMIT", "3/minute")
    monkeypatch.setattr(
        rate_limit,
        "EXEMPT_FROM_DEFAULT_LIMIT",
        EXEMPT_FROM_DEFAULT_LIMIT | {f"{__name__}.exenta_del_test"},
    )
    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()
    yield TestClient(_app())
    limiter.reset()


def _con_sesion(user_id: str | None = None) -> dict[str, str]:
    """La cookie de acceso de un usuario."""
    token = create_access_token({"sub": user_id or str(uuid4())})
    return {"cookie": f"access_token={token}"}


def test_default_limit_on_route_without_own_limit_rejects_the_next_request(cliente):
    """
    Given: Un usuario con sesión y una ruta sin límite propio, con el límite por defecto a 3/minuto
    When: Hace 4 peticiones
    Then: Las 3 primeras pasan y la cuarta da 429
    """
    cabeceras = _con_sesion()

    codigos = [cliente.get("/sin-limite", headers=cabeceras).status_code for _ in range(4)]

    assert codigos == [200, 200, 200, 429]


def test_default_limit_skips_routes_with_their_own_limit(cliente):
    """
    Given: Una ruta con su propio @limiter.limit (50/minuto) y el de por defecto a 3/minuto
    When: El mismo usuario hace 6 peticiones
    Then: Todas pasan: cuenta solo su límite, no además el de por defecto
    """
    cabeceras = _con_sesion()

    codigos = {cliente.get("/con-limite", headers=cabeceras).status_code for _ in range(6)}

    assert codigos == {200}


def test_default_limit_counts_each_user_separately(cliente):
    """
    Given: Dos usuarios con sesión desde la misma red
    When: El primero agota el límite por defecto
    Then: El segundo sigue pasando: con sesión cuenta el usuario, no la red
    """
    uno, otro = _con_sesion(), _con_sesion()
    for _ in range(3):
        cliente.get("/sin-limite", headers=uno)

    assert cliente.get("/sin-limite", headers=uno).status_code == 429
    assert cliente.get("/sin-limite", headers=otro).status_code == 200


def test_default_limit_without_verified_user_is_not_counted(cliente):
    """
    Given: Peticiones sin sesión o con el acceso caducado, todas desde la misma red
    When: Se hacen 6, por encima del límite por defecto de 3/minuto
    Then: Ninguna da 429: sin usuario verificado no se cuenta (revisor, 5 nov). Con la
          clave de red, que sin la IP real es toda la app, un acceso caducado recibía 429
          en vez de su 401 y el front nunca refrescaba la sesión
    """
    caducado = jwt.encode(
        {"sub": str(uuid4()), "type": "access", "exp": int(time.time()) - 60},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    sin_sesion = {"X-Test-Client-ID": "red-a"}
    con_caducado = {"X-Test-Client-ID": "red-a", "cookie": f"access_token={caducado}"}

    codigos = {
        cliente.get("/sin-limite", headers=h).status_code for h in [sin_sesion, con_caducado] * 3
    }

    assert codigos == {200}


def test_default_limit_counts_each_route_separately(cliente):
    """
    Given: Un usuario que agota el límite por defecto en una ruta
    When: Pide otra ruta sin límite propio
    Then: Pasa: cada ruta tiene su contador, y un sondeo no deja sin servicio a las demás
    """
    cabeceras = _con_sesion()
    for _ in range(3):
        cliente.get("/sin-limite", headers=cabeceras)

    assert cliente.get("/sin-limite", headers=cabeceras).status_code == 429
    assert cliente.get("/otra-sin-limite", headers=cabeceras).status_code == 200


def test_default_limit_dependency_is_async():
    """
    Given: La dependencia del límite por defecto
    When: Se mira cómo la ejecuta FastAPI
    Then: Es async: una síncrona saltaría al pool de hilos en cada petición, y PRO va justo de CPU
    """
    assert inspect.iscoroutinefunction(apply_default_rate_limit)


def test_default_limit_skips_exempt_routes(cliente):
    """
    Given: Una ruta declarada exenta
    When: El mismo usuario hace 6 peticiones
    Then: Todas pasan
    """
    cabeceras = _con_sesion()

    codigos = {cliente.get("/exenta", headers=cabeceras).status_code for _ in range(6)}

    assert codigos == {200}


def test_default_limit_429_has_the_same_body_as_slowapi(cliente):
    """
    Given: Un usuario que agota el límite por defecto
    When: Hace una petición más
    Then: El 429 tiene el mismo cuerpo que el de un @limiter.limit, con el límite que saltó
    """
    cabeceras = _con_sesion()
    for _ in range(3):
        cliente.get("/sin-limite", headers=cabeceras)

    respuesta = cliente.get("/sin-limite", headers=cabeceras)

    assert respuesta.status_code == 429
    assert respuesta.json() == {"error": "Rate limit exceeded: 3 per 1 minute"}


def test_default_limit_with_disabled_limiter_counts_nothing(cliente, monkeypatch):
    """
    Given: El limiter apagado, como en los tests de integración
    When: El mismo usuario hace 6 peticiones a una ruta sin límite propio
    Then: Todas pasan
    """
    monkeypatch.setattr(limiter, "enabled", False)
    cabeceras = _con_sesion()

    codigos = {cliente.get("/sin-limite", headers=cabeceras).status_code for _ in range(6)}

    assert codigos == {200}


def test_default_limit_is_100_per_minute():
    """
    Given: La configuración real
    When: Se mira el límite por defecto
    Then: Es 100/minuto, el que ya figuraba (y nunca se aplicaba)
    """
    assert rate_limit.DEFAULT_LIMIT == "100/minute"


def test_exempt_routes_are_exactly_the_agreed_ones():
    """
    Given: La lista de exentas del límite por defecto
    When: Se compara con la acordada (5 nov 2026)
    Then: Es esa y solo esa: health y raíz (Render), la documentación, y los datos estáticos
    """
    assert {
        "main.root",
        "main.health",
        "main.get_documentation",
        "main.get_redoc_documentation",
        "src.modules.user.infrastructure.api.v1.avatar_routes.list_avatar_presets",
        "src.modules.user.infrastructure.api.v1.avatar_routes.get_avatar_preset_image",
        "src.shared.infrastructure.api.v1.country_routes.list_countries",
        "src.shared.infrastructure.api.v1.country_routes.list_adjacent_countries",
    } == EXEMPT_FROM_DEFAULT_LIMIT


def _peticion_con_cookies(cookies: str = "", cliente: str | None = None) -> Request:
    """Una petición con estas cookies, y X-Test-Client-ID si se pide."""
    cabeceras = [(b"cookie", cookies.encode())] if cookies else []
    if cliente:
        cabeceras.append((b"x-test-client-id", cliente.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/refresh-token",
            "query_string": b"",
            "headers": cabeceras,
            "client": ("10.9.9.9", 1),
        }
    )


def test_refresh_key_with_valid_refresh_cookie_is_its_user():
    """
    Given: Una cookie de refresh válida (el acceso ya caducó: es cuando se refresca)
    When: Se calcula la clave del límite del refresco
    Then: Es la del usuario de ese refresh, no la de red (que en producción es toda la app)
    """
    user_id = str(uuid4())
    refresco = create_refresh_token({"sub": user_id})

    assert refresh_token_rate_limit_key(_peticion_con_cookies(f"refresh_token={refresco}")) == (
        f"user:{user_id}"
    )


@pytest.mark.parametrize("cookie", ["", "refresh_token=basura"])
def test_refresh_key_without_valid_refresh_cookie_is_the_network(cookie):
    """
    Given: Sin cookie de refresh, o con una inventada
    When: Se calcula la clave del límite del refresco
    Then: Es la de red: un token falso no elige contador
    """
    peticion = _peticion_con_cookies(cookie, cliente="red-del-test")

    assert refresh_token_rate_limit_key(peticion) == "red-del-test"


def test_refresh_key_ignores_an_access_token_in_the_refresh_cookie():
    """
    Given: Un access token (otro tipo de JWT) puesto en la cookie de refresh
    When: Se calcula la clave del límite del refresco
    Then: Es la de red: solo cuenta un refresh de verdad
    """
    acceso = create_access_token({"sub": str(uuid4())})
    peticion = _peticion_con_cookies(f"refresh_token={acceso}", cliente="red-del-test")

    assert refresh_token_rate_limit_key(peticion) == "red-del-test"


def test_refresh_limit_is_30_per_user_and_600_per_network():
    """
    Given: El límite del refresco, que depende de la clave
    When: Se pide con la clave de un usuario o con la de red
    Then: 30/minuto por usuario; 600 por red: sin cookie válida van todos los visitantes
          anónimos, y sin la IP real son un contador para toda la app (revisor, 5 nov)
    """
    assert limite_del_refresco("user:123") == "30/minute"
    assert limite_del_refresco("10.0.0.1") == "600/minute"
