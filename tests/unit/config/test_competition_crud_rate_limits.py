"""
Cuántas veces se puede crear, editar y borrar una competición.

Editar tenía 10 por HORA, como crear y borrar. Un organizador que monta su
torneo retoca fechas, cupo y países, y cada rechazo de la API también cuenta:
en la prueba en bloque del 4 oct 2026 se agotó editando una sola competición.
Decidido por Agustín ese día: editar pasa a 10 por minuto, como el resto de
modificaciones; crear y borrar siguen por hora, que ahí frenan el abuso.
"""

from main import app  # noqa: F401 - monta las rutas y registra sus límites
from src.config.rate_limit import limiter

_RUTAS = "src.modules.competition.infrastructure.api.v1.competition_crud_routes"


def _limites(funcion: str) -> list[str]:
    return [str(limite.limit) for limite in limiter._route_limits[f"{_RUTAS}.{funcion}"]]


def test_r1_editar_una_competicion_admite_10_por_minuto():
    assert _limites("update_competition") == ["10 per 1 minute"]


def test_r2_crear_y_borrar_siguen_en_10_por_hora():
    assert _limites("create_competition") == ["10 per 1 hour"]
    assert _limites("delete_competition") == ["10 per 1 hour"]
