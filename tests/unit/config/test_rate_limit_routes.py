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
from src.config.dependencies import get_current_user
from src.config.rate_limit import get_client_identifier, get_rate_limit_key, limiter


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
    rows = []
    for route in _routes(app.routes):
        name = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        limits = limiter._route_limits.get(name)
        if limits:
            requires_session = get_current_user in set(_dependencies(route.dependant))
            rows.append((route, limits, requires_session))
    return rows


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
    Then: Todas cuentan por usuario
    """
    wrong = [
        _label(route)
        for route, limits, requires_session in _limited_routes()
        if requires_session and any(lim.key_func is not get_rate_limit_key for lim in limits)
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
        if not requires_session and any(lim.key_func is not get_client_identifier for lim in limits)
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
