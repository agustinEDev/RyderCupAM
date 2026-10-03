"""
Pedir equipos a un torneo que no los tiene es un 400 con su motivo (#251).

Nueve rutas de la Ryder (capitanes, subcapitán, draft, sobres, clasificación,
vista de anotación…) pueden recibir un Stableford, y la mayoría no traduce
ValueError: sin esto sería un 500. Se traduce en un solo sitio.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.modules.competition.domain.entities.competition import TournamentTypeError
from src.modules.competition.infrastructure.api.exception_handlers import (
    register_competition_exception_handlers,
)

pytestmark = pytest.mark.asyncio


async def test_un_tournament_type_error_es_un_400_con_su_motivo():
    app = FastAPI()
    register_competition_exception_handlers(app)

    @app.get("/sobre")
    async def sobre():
        raise TournamentTypeError("Un Stableford no tiene equipos")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        respuesta = await client.get("/sobre")

    assert respuesta.status_code == 400
    assert respuesta.json() == {"detail": "Un Stableford no tiene equipos"}


def test_la_app_lo_registra():
    from main import app

    assert TournamentTypeError in app.exception_handlers
