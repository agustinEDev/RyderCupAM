"""
Pedir equipos a un torneo que no los tiene es un 400 con su motivo (#251).

Nueve rutas de la Ryder (capitanes, subcapitán, draft, sobres, clasificación,
vista de anotación…) pueden recibir un Stableford, y la mayoría no traduce
ValueError: sin esto sería un 500. Se traduce en un solo sitio: el mapa de
errores de competición (ADR-049), igual que unos ajustes de stroke play sin sentido.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.modules.competition.domain.entities.competition import TournamentTypeError
from src.modules.competition.domain.value_objects.stroke_play_setup import (
    StrokePlaySettingsError,
)
from src.modules.competition.infrastructure.api.codigos_de_error import CODIGOS
from src.shared.infrastructure.http.codigos_de_error import registra_los_codigos

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "error",
    [
        TournamentTypeError("Un Stableford no tiene equipos"),
        StrokePlaySettingsError("Un Stableford no tiene equipos"),
    ],
)
async def test_a_tournament_without_that_feature_answers_400_with_its_reason(error):
    """
    Given: El mapa de errores de competición
    When: Una ruta deja salir el error de un torneo que no admite lo pedido
    Then: 400 con el motivo como detail
    """
    app = FastAPI()
    registra_los_codigos(app, CODIGOS)

    @app.get("/sobre")
    async def sobre():
        raise error

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        respuesta = await client.get("/sobre")

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "Un Stableford no tiene equipos"}


def test_la_app_lo_registra():
    from main import app

    assert TournamentTypeError in app.exception_handlers
    assert StrokePlaySettingsError in app.exception_handlers
