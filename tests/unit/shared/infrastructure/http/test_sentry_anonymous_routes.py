"""
Las rutas de muestras de hoyo, anónimas también para Sentry (BE #532, 16 oct 2026).

El middleware de Sentry no pone usuario en las rutas que reconoce
`is_anonymous_path`. Si se renombra una de esas rutas y nadie toca el patrón,
Sentry volvería a saber quién manda las muestras: este test recorre las rutas
reales de la app y lo impide.

| Caso                                 | Resultado                                  |
|--------------------------------------|--------------------------------------------|
| Las rutas de muestras de la app      | Hay dos (POST y GET), y las dos son anónimas |
| La de reportar un hoyo (entrega 7)   | POST, anónima                               |
| Otras rutas del mapa de hoyos        | No son anónimas                             |
"""

from collections.abc import Iterator

from fastapi.routing import APIRoute

from main import app
from src.shared.infrastructure.http.sentry_middleware import is_anonymous_path

# Desde la entrega 7 (18 oct), también el reporte de un hoyo: tampoco se guarda quién
SAMPLE_ENDPOINTS = {"submit_hole_sample", "list_hole_samples", "submit_hole_report"}


def _routes(routes, prefix: str = "") -> Iterator[tuple[str, APIRoute]]:
    """Cada ruta con la ruta que de verdad sirve la app (con el prefijo del include)."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
        elif hasattr(route, "original_router"):
            yield from _routes(route.original_router.routes, prefix + route.include_context.prefix)
        elif hasattr(route, "routes"):
            yield from _routes(route.routes, prefix)


def _sample_routes() -> list[tuple[str, APIRoute]]:
    return [
        (path, route)
        for path, route in _routes(app.routes)
        if route.endpoint.__name__ in SAMPLE_ENDPOINTS
    ]


def test_every_samples_route_is_anonymous_for_sentry():
    """
    GIVEN: Las rutas de la app que atienden las muestras (por su función, no por su ruta)
    WHEN: Se pasa cada ruta por `is_anonymous_path`
    THEN: Son tres (las dos de muestras y la del reporte) y todas son anónimas
    """
    routes = _sample_routes()

    assert sorted(m for _, route in routes for m in route.methods) == ["GET", "POST", "POST"]
    assert all(path.startswith("/api/v1/") for path, _ in routes)
    assert [path for path, _ in routes if not is_anonymous_path(path)] == []


def test_other_hole_map_routes_are_not_anonymous():
    """
    GIVEN: El mapa del campo y su revisión
    WHEN: Se pasan por `is_anonymous_path`
    THEN: No son anónimas (el patrón no se come de más)
    """
    for path in (
        "/api/v1/golf-courses/{golf_course_id}/hole-map",
        "/api/v1/golf-courses/admin/{golf_course_id}/hole-map",
        "/api/v1/golf-courses/{golf_course_id}/hole-map/samples-admin",
        "/api/v1/golf-courses/{golf_course_id}/hole-map/samples/1/extra",
    ):
        assert is_anonymous_path(path) is False
