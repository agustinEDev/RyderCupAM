"""
El tipo de torneo por la API (RyderCupAM#251).

El frontend de hoy no manda el tipo: tiene que seguir creando la Ryder de
siempre. Un Stableford o un Medal se crea sin nada de la Ryder, y lo que solo
existe en una Ryder (capitanes, clasificación por equipos, sus equipos) se le
niega con un 400 que dice por qué, nunca con un 500.
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


def _datos(**extra) -> dict:
    start = date.today() + timedelta(days=30)
    datos = {
        "name": f"Torneo {uuid.uuid4().hex[:8]}",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=1)).isoformat(),
        "main_country": "ES",
        "play_mode": "HANDICAP",
    }
    datos.update(extra)
    return datos


async def _organizador(client: AsyncClient) -> dict:
    usuario = await create_authenticated_user(
        client, f"tipo-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Tipo", "Torneo"
    )
    set_auth_cookies(client, usuario["cookies"])
    # Un Stableford o un Medal exige hándicap para crearlo (#251, 7 oct 2026)
    respuesta = await client.post(
        "/api/v1/handicaps/update", json={"user_id": usuario["user"]["id"], "manual_handicap": 15.0}
    )
    assert respuesta.status_code == 200, respuesta.text
    return usuario


async def test_sin_tipo_se_crea_la_ryder_de_siempre(client: AsyncClient):
    usuario = await _organizador(client)

    creada = await create_competition(client, usuario["cookies"], _datos())

    assert creada["tournament_type"] == "RYDER_CUP"
    assert creada["modality"] == "MATCH_PLAY"
    assert (creada["team_1_name"], creada["team_2_name"]) == ("Team 1", "Team 2")
    assert creada["setup_mode"] == "RYDER_CUP"


@pytest.mark.parametrize("tipo", ["STABLEFORD", "MEDAL"])
async def test_un_torneo_de_stroke_play_se_crea_y_se_lee_sin_nada_de_la_ryder(
    client: AsyncClient, tipo
):
    usuario = await _organizador(client)

    creada = await create_competition(client, usuario["cookies"], _datos(tournament_type=tipo))
    ficha = (await client.get(f"/api/v1/competitions/{creada['id']}")).json()

    for respuesta in (creada, ficha):
        assert respuesta["tournament_type"] == tipo
        assert respuesta["modality"] == "STROKE_PLAY"
        assert respuesta["team_1_name"] is None
        assert respuesta["team_2_name"] is None
        assert respuesta["setup_mode"] is None
        assert respuesta["team_assignment"] is None


async def test_un_stableford_con_equipos_es_un_400_con_su_motivo(client: AsyncClient):
    await _organizador(client)

    respuesta = await client.post(
        "/api/v1/competitions", json=_datos(tournament_type="STABLEFORD", team_1_name="Europa")
    )

    assert respuesta.status_code == 400, respuesta.text
    assert "no tiene equipos" in respuesta.json()["detail"]


class TestLoQueSoloExisteEnUnaRyder:
    """Con un Stableford: 400 con el motivo, no 500."""

    async def _stableford(self, client: AsyncClient) -> dict:
        usuario = await _organizador(client)
        return await create_competition(
            client, usuario["cookies"], _datos(tournament_type="STABLEFORD")
        )

    async def test_nombrar_capitanes(self, client: AsyncClient):
        torneo = await self._stableford(client)

        respuesta = await client.put(
            f"/api/v1/competitions/{torneo['id']}/captains",
            json={"team_a_captain_id": str(uuid.uuid4()), "team_b_captain_id": str(uuid.uuid4())},
        )

        assert respuesta.status_code == 400, respuesta.text
        assert "no tiene equipos" in respuesta.json()["detail"]

    async def test_la_clasificacion_llega_con_sus_rondas(self, client: AsyncClient):
        # El motivo habla de la clasificación, no de los equipos (Agustín, 4 oct 2026)
        torneo = await self._stableford(client)

        respuesta = await client.get(f"/api/v1/competitions/{torneo['id']}/leaderboard")

        assert respuesta.status_code == 400, respuesta.text
        assert respuesta.json()["detail"] == (
            "La clasificación de un Stableford llega con sus rondas: todavía no se puede consultar"
        )

    async def test_ponerle_equipos_al_editarlo(self, client: AsyncClient):
        torneo = await self._stableford(client)

        respuesta = await client.put(
            f"/api/v1/competitions/{torneo['id']}", json={"team_1_name": "Europa"}
        )

        assert respuesta.status_code == 400, respuesta.text
        assert "no tiene equipos" in respuesta.json()["detail"]
