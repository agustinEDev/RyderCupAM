"""
Lo jugado de una privada, por la API (tabla del 27 oct 2026).

La regla la cubren los tests de la puerta; aquí, que cada ruta le pregunta lo
suyo y que su «no» es un 403 con su código antes de leer nada más.
"""

import uuid
from datetime import date, timedelta
from typing import ClassVar

import pytest
from httpx import AsyncClient

from src.modules.competition.application.services.lo_jugado_de_una_privada import (
    NoPuedeVerloError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


class _Puerta:
    """Apunta qué le preguntan; con `cierra`, dice que no."""

    llamadas: ClassVar[list] = []
    cierra: ClassVar[bool] = True

    def _apunta(self, metodo, ident, quien, es_admin):
        type(self).llamadas.append((metodo, ident, str(quien.value), es_admin))
        if type(self).cierra:
            raise NoPuedeVerloError

    async def exigir_la_clasificacion(self, competition_id, quien, *, es_admin=False):
        self._apunta("clasificacion", competition_id, quien, es_admin)

    async def exigir_la_clasificacion_de_la_ronda(self, round_id, quien, *, es_admin=False):
        self._apunta("ronda", round_id, quien, es_admin)

    async def exigir_el_partido(self, match_id, quien, *, es_admin=False):
        self._apunta("partido", match_id, quien, es_admin)

    async def exigir_la_partida(self, partida_id, quien, *, es_admin=False):
        self._apunta("partida", partida_id, quien, es_admin)


ID = uuid.UUID("7a1e0c3e-27a0-4c1d-9f00-000000000027")
RUTAS = [
    (f"/api/v1/competitions/{ID}/leaderboard", "clasificacion", CompetitionId(ID)),
    (f"/api/v1/competitions/{ID}/standings", "clasificacion", CompetitionId(ID)),
    (f"/api/v1/competitions/{ID}/standings/scratch", "clasificacion", CompetitionId(ID)),
    (f"/api/v1/competitions/rounds/{ID}/standings", "ronda", RoundId(ID)),
    (f"/api/v1/competitions/matches/{ID}", "partido", MatchId(ID)),
    (f"/api/v1/competitions/matches/{ID}/scoring-view", "partido", MatchId(ID)),
    (f"/api/v1/competitions/groups/{ID}/scoring-view", "partida", PartidaId(ID)),
]


@pytest.fixture
async def con_la_puerta(client: AsyncClient):
    from main import app
    from src.config.dependencies import get_puerta_de_lo_jugado

    yo = await create_authenticated_user(
        client, f"lj_{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Mira", "Fuera"
    )
    set_auth_cookies(client, yo["cookies"])
    _Puerta.llamadas = []
    app.dependency_overrides[get_puerta_de_lo_jugado] = _Puerta
    try:
        yield yo
    finally:
        app.dependency_overrides.pop(get_puerta_de_lo_jugado, None)
        _Puerta.cierra = True


@pytest.mark.parametrize(("ruta", "metodo", "ident"), RUTAS)
async def test_6_cerrada_es_un_403_con_su_codigo(client, con_la_puerta, ruta, metodo, ident):
    _Puerta.cierra = True

    r = await client.get(ruta)

    assert r.status_code == 403, r.text
    assert r.json()["error_code"] == "PRIVATE_COMPETITION"
    assert _Puerta.llamadas == [(metodo, ident, con_la_puerta["user"]["id"], False)]


@pytest.mark.parametrize(("ruta", "metodo", "ident"), RUTAS)
async def test_abierta_sigue_a_su_caso_de_uso(client, con_la_puerta, ruta, metodo, ident):
    """Con la puerta abierta llega a su caso de uso, que dice lo suyo del id inventado."""
    _Puerta.cierra = False

    r = await client.get(ruta)

    assert r.status_code != 403, r.text
    assert [m for m, *_ in _Puerta.llamadas] == [metodo]


# --- De verdad, con la puerta real --------------------------------------------------


async def _jugador(client: AsyncClient, nombre: str) -> dict:
    return await create_authenticated_user(
        client,
        f"ljr_{nombre.lower()}_{uuid.uuid4().hex[:6]}@test.com",
        "P@ssw0rd123!",
        nombre,
        "Real",
    )


def _datos(visibilidad: str, stroke_play: bool) -> dict:
    start = date.today() + timedelta(days=30)
    datos = {
        "name": f"LJ {uuid.uuid4().hex[:8]}",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=1)).isoformat(),
        "main_country": "ES",
        "play_mode": "HANDICAP",
        "max_players": 12,
        "visibility": visibilidad,
    }
    if stroke_play:
        return {
            **datos,
            "tournament_type": "STABLEFORD",
            "stroke_play": {"category_limits": [36.0]},
        }
    return {**datos, "team_assignment": "MANUAL"}


async def _mira(client: AsyncClient, quien: dict, ruta: str) -> int:
    set_auth_cookies(client, quien["cookies"])
    return (await client.get(ruta)).status_code


async def test_6_la_clasificacion_ryder_de_una_privada_cerrada_a_quien_no_esta(client):
    creador, curioso = await _jugador(client, "Org"), await _jugador(client, "Curioso")
    privada = await create_competition(client, creador["cookies"], _datos("PRIVATE", False))
    publica = await create_competition(client, creador["cookies"], _datos("PUBLIC", False))

    assert await _mira(client, curioso, f"/api/v1/competitions/{privada['id']}/leaderboard") == 403
    assert await _mira(client, creador, f"/api/v1/competitions/{privada['id']}/leaderboard") == 200
    assert await _mira(client, curioso, f"/api/v1/competitions/{publica['id']}/leaderboard") == 200


async def test_6_las_clasificaciones_de_stroke_play_de_una_privada_tambien(client):
    creador, curioso = await _jugador(client, "Orga"), await _jugador(client, "Curiosa")
    # Un Stableford exige el hándicap de quien lo crea: juega en él
    set_auth_cookies(client, creador["cookies"])
    r = await client.post(
        "/api/v1/handicaps/update", json={"user_id": creador["user"]["id"], "manual_handicap": 15.0}
    )
    assert r.status_code == 200, r.text
    privada = await create_competition(client, creador["cookies"], _datos("PRIVATE", True))
    publica = await create_competition(client, creador["cookies"], _datos("PUBLIC", True))

    for ruta in ("standings", "standings/scratch"):
        assert await _mira(client, curioso, f"/api/v1/competitions/{privada['id']}/{ruta}") == 403
        assert await _mira(client, creador, f"/api/v1/competitions/{privada['id']}/{ruta}") == 200
        assert await _mira(client, curioso, f"/api/v1/competitions/{publica['id']}/{ruta}") == 200
