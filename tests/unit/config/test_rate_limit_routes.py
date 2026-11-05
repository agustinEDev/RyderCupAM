"""
Qué contador usa cada ruta con límite (RyderCupAM#273).

Recorre las rutas reales de la app. Una ruta que exige sesión cuenta por usuario;
una anónima, por red. Si mañana se añade una ruta anónima con límite y nadie le
pone la clave de red, la de usuario le daría a quien tenga sesión un contador
propio en, por ejemplo, el login de otra cuenta: este test lo impide.
"""

from collections.abc import Iterator

from fastapi.routing import APIRoute

from main import app
from src.config.dependencies import get_current_user, get_current_user_optional
from src.config.rate_limit import (
    EXEMPT_FROM_DEFAULT_LIMIT,
    apply_default_rate_limit,
    get_client_identifier,
    get_hole_sample_rate_limit_key,
    get_rate_limit_key,
    limite_de_lo_publico,
    limiter,
    refresh_token_rate_limit_key,
)

# Rutas con sesión que cuentan por usuario sin decir quién en el log (BE #532 y,
# desde la entrega 7, el reporte de un hoyo)
ANONYMOUS_USER_KEYS = {
    "submit_hole_sample": get_hole_sample_rate_limit_key,
    "submit_hole_report": get_hole_sample_rate_limit_key,
}


# Anónimas que no cuentan por red: el refresco llega con el acceso ya caducado, y
# por red sería un contador para toda la app en producción (BE #467)
ANONYMOUS_ROUTE_KEYS = {"refresh_access_token": refresh_token_rate_limit_key}


# Públicas que cuentan por usuario si llega un token válido, y si no por red: no
# piden sesión para que una caducada no las rompa (resumen público, 28 oct 2026)
PUBLICAS_POR_USUARIO = {"get_competition_summary"}


def _routes(routes) -> Iterator[APIRoute]:
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from _routes(route.original_router.routes)
        elif hasattr(route, "routes"):
            yield from _routes(route.routes)


def _dependencies(dependant) -> Iterator:
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _dependencies(dependency)


def _limited_routes() -> list[tuple[APIRoute, list, bool]]:
    """Las rutas con límite, sus límites y si cuentan como con sesión."""
    rows = []
    for route in _routes(app.routes):
        name = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        # Los que dependen de la clave (lo público, 28 oct 2026) van aparte
        limits = limiter._route_limits.get(name) or limiter._dynamic_route_limits.get(name)
        if limits:
            # Con sesión opcional (la clasificación por enlace, release social 3)
            # cuenta como con sesión: por usuario, y por red si no la hay
            dependencias = set(_dependencies(route.dependant))
            requires_session = bool({get_current_user, get_current_user_optional} & dependencias)
            rows.append((route, limits, requires_session))
    return rows


def _clave(limite):
    """La función de clave de un límite, fijo (`key_func`) o según la clave (`key_function`)."""
    return getattr(limite, "key_func", None) or limite.key_function


def _label(route: APIRoute) -> str:
    return f"{sorted(route.methods)[0]} {route.path}"


def test_there_are_limited_routes_of_both_kinds():
    """
    Given: La app montada
    When: Se recorren sus rutas con límite
    Then: Hay de los dos tipos; si no, los otros tests no comprobarían nada
    """
    rows = _limited_routes()

    assert any(requires_session for _, _, requires_session in rows)
    assert any(not requires_session for _, _, requires_session in rows)


def test_every_limited_route_with_session_counts_per_user():
    """
    Given: Las rutas con límite que exigen sesión
    When: Se mira la clave de cada límite
    Then: Todas cuentan por usuario (la de muestras de hoyo, con su clave sin el id)
    """
    wrong = [
        _label(route)
        for route, limits, requires_session in _limited_routes()
        if requires_session
        and any(
            _clave(lim) is not ANONYMOUS_USER_KEYS.get(route.endpoint.__name__, get_rate_limit_key)
            for lim in limits
        )
    ]

    assert wrong == []


def test_every_limited_anonymous_route_counts_per_network():
    """
    Given: Las rutas con límite que no exigen sesión
    When: Se mira la clave de cada límite
    Then: Todas cuentan por red, aunque quien llame tenga sesión
    """
    wrong = [
        _label(route)
        for route, limits, requires_session in _limited_routes()
        if not requires_session
        and route.endpoint.__name__ not in PUBLICAS_POR_USUARIO
        and any(
            _clave(lim)
            is not ANONYMOUS_ROUTE_KEYS.get(route.endpoint.__name__, get_client_identifier)
            for lim in limits
        )
    ]

    assert wrong == []


def test_refresh_mine_has_its_own_per_user_limit():
    """
    Given: POST /handicaps/refresh-mine, que puede llamar a la RFEG (hasta 10 s)
    When: Se buscan sus límites
    Then: Tiene uno propio por usuario (la mitad pendiente de RyderCupAM#341)
    """
    labels = {
        _label(route): limits
        for route, limits, requires_session in _limited_routes()
        if requires_session
    }

    assert any(label.endswith("/refresh-mine") for label in labels)


def test_every_route_a_visitor_can_reach_has_a_limit():
    """
    Given: Las rutas con sesión opcional (lo que ve un visitante, release social 3)
    When: Se buscan sus límites
    Then: Todas tienen uno, por usuario o por red: abiertas sin él, eran gratis
    """
    sin_limite = []
    for route in _routes(app.routes):
        if get_current_user_optional not in set(_dependencies(route.dependant)):
            continue
        name = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        if not (limiter._route_limits.get(name) or limiter._dynamic_route_limits.get(name)):
            sin_limite.append(_label(route))

    assert sin_limite == []


def test_lo_publico_cuenta_distinto_con_y_sin_sesion():
    """
    Given: El límite de lo que ve un visitante (/code-review, 28 oct 2026)
    When: Se pide con la clave de un usuario o con la de red
    Then: Con sesión, el de siempre; sin ella, con margen (contador compartido, ADR-038)
    """
    assert limite_de_lo_publico("user:123") == "30/minute"
    assert limite_de_lo_publico("10.0.0.1") == "600/minute"


def _limites_de(nombre: str) -> list:
    """Los límites propios de la ruta cuyo endpoint se llama así."""
    for route in _routes(app.routes):
        if route.endpoint.__name__ == nombre:
            completo = f"{route.endpoint.__module__}.{nombre}"
            return limiter._route_limits.get(completo) or []
    raise AssertionError(f"no hay ruta {nombre}")


def test_the_default_limit_is_a_global_dependency_of_the_app():
    """
    Given: La app montada
    When: Se miran sus dependencias globales
    Then: Incluye el límite por defecto: lo heredan todas las rutas, también las nuevas (BE #467)
    """
    assert apply_default_rate_limit in [d.dependency for d in app.router.dependencies]


def test_an_included_route_without_own_limit_gets_429_from_the_default_limit(monkeypatch):
    """
    Given: La app real, el límite por defecto a 3/minuto y una ruta incluida sin límite propio
    When: La misma red pide 5 veces GET /api/v1/users/me/devices sin sesión
    Then: Las 3 primeras dan su 401 y las siguientes 429: la dependencia global llega a las
          rutas de los routers incluidos (el middleware de slowapi no llegaba)
    """
    from fastapi.testclient import TestClient

    from src.config import rate_limit

    monkeypatch.setattr(rate_limit, "DEFAULT_LIMIT", "3/minute")
    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()
    cliente = TestClient(app)
    cabeceras = {"X-Test-Client-ID": "guardian-del-limite-por-defecto"}

    codigos = [
        cliente.get("/api/v1/users/me/devices", headers=cabeceras).status_code for _ in range(5)
    ]

    limiter.reset()
    assert codigos == [401, 401, 401, 429, 429]


def test_every_exempt_route_exists_and_has_no_own_limit():
    """
    Given: La lista de exentas del límite por defecto
    When: Se busca cada una entre las rutas de la app
    Then: Todas existen (un nombre viejo no exime a nadie en silencio) y ninguna tiene límite propio
    """
    rutas = {f"{r.endpoint.__module__}.{r.endpoint.__name__}" for r in _routes(app.routes)}

    assert rutas >= EXEMPT_FROM_DEFAULT_LIMIT
    assert not EXEMPT_FROM_DEFAULT_LIMIT & set(limiter._route_limits)


def test_refresh_token_has_its_own_limit_per_refresh_user():
    """
    Given: POST /auth/refresh-token, que llega con el acceso ya caducado
    When: Se miran sus límites
    Then: Tiene uno propio de 30/minuto que cuenta por el usuario del refresh
    """
    limites = _limites_de("refresh_access_token")

    assert [str(lim.limit) for lim in limites] == ["30 per 1 minute"]
    assert all(_clave(lim) is refresh_token_rate_limit_key for lim in limites)


def test_verify_email_has_its_own_limit_per_network():
    """
    Given: POST /auth/verify-email, anónima
    When: Se miran sus límites
    Then: Tiene uno propio de 30/hora por red, como reset-password
    """
    limites = _limites_de("verify_email")

    assert [str(lim.limit) for lim in limites] == ["30 per 1 hour"]
    assert all(_clave(lim) is get_client_identifier for lim in limites)
