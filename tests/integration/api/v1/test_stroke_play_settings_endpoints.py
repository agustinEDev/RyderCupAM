"""
Los ajustes del stroke play por la API (RyderCupAM#251).

Al crear viajan dentro de `stroke_play`; para cambiarlos hay un
`PATCH /competitions/{id}/stroke-play` propio, hasta que la competición
empieza. Una Ryder no los tiene: 400 con el motivo. Los límites viajan como
texto (`"12.0"`), igual que el hándicap personalizado.
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
        "tournament_type": "STABLEFORD",
    }
    datos.update(extra)
    return datos


async def _usuario(client: AsyncClient) -> dict:
    usuario = await create_authenticated_user(
        client, f"sp-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Stroke", "Play"
    )
    set_auth_cookies(client, usuario["cookies"])
    return usuario


def _limites(respuesta: dict) -> list[float]:
    return [float(v) for v in respuesta["stroke_play"]["category_limits"]]


class TestAlCrear:
    async def test_un_stableford_con_sus_ajustes_los_devuelve_al_crear_y_en_la_ficha(
        self, client: AsyncClient
    ):
        usuario = await _usuario(client)

        creada = await create_competition(
            client,
            usuario["cookies"],
            _datos(
                stroke_play={
                    "category_limits": [12.0, 26.0],
                    "max_matchdays_per_player": 2,
                    "overall_standing": "BEST_CARD",
                }
            ),
        )
        ficha = (await client.get(f"/api/v1/competitions/{creada['id']}")).json()

        for respuesta in (creada, ficha):
            assert _limites(respuesta) == [12.0, 26.0]
            assert respuesta["stroke_play"]["max_matchdays_per_player"] == 2
            assert respuesta["stroke_play"]["overall_standing"] == "BEST_CARD"

    async def test_un_medal_sin_ajustes_tiene_los_de_por_defecto(self, client: AsyncClient):
        usuario = await _usuario(client)

        creada = await create_competition(
            client, usuario["cookies"], _datos(tournament_type="MEDAL")
        )

        assert creada["stroke_play"] == {
            "category_limits": [],
            "max_matchdays_per_player": 1,
            "overall_standing": "ACCUMULATED",
        }

    async def test_una_ryder_no_los_trae(self, client: AsyncClient):
        usuario = await _usuario(client)

        creada = await create_competition(
            client, usuario["cookies"], _datos(tournament_type="RYDER_CUP")
        )

        assert creada["stroke_play"] is None

    async def test_una_ryder_con_ajustes_es_un_400_con_su_motivo(self, client: AsyncClient):
        await _usuario(client)

        respuesta = await client.post(
            "/api/v1/competitions",
            json=_datos(tournament_type="RYDER_CUP", stroke_play={"category_limits": [12.0]}),
        )

        assert respuesta.status_code == 400, respuesta.text
        assert "no tiene categorías" in respuesta.json()["detail"]

    async def test_limites_desordenados_son_un_400_con_su_motivo(self, client: AsyncClient):
        await _usuario(client)

        respuesta = await client.post(
            "/api/v1/competitions", json=_datos(stroke_play={"category_limits": [26.0, 12.0]})
        )

        assert respuesta.status_code == 400, respuesta.text
        assert "de menor a mayor" in respuesta.json()["detail"]


class TestAlCambiar:
    async def _stableford(self, client: AsyncClient) -> tuple[dict, dict]:
        usuario = await _usuario(client)
        creada = await create_competition(client, usuario["cookies"], _datos())
        return usuario, creada

    async def test_el_creador_los_cambia_y_la_ficha_lo_ensena(self, client: AsyncClient):
        _, creada = await self._stableford(client)

        respuesta = await client.patch(
            f"/api/v1/competitions/{creada['id']}/stroke-play",
            json={"category_limits": [18.0]},
        )
        ficha = (await client.get(f"/api/v1/competitions/{creada['id']}")).json()

        assert respuesta.status_code == 200, respuesta.text
        assert [float(v) for v in respuesta.json()["category_limits"]] == [18.0]
        assert _limites(ficha) == [18.0]
        assert ficha["stroke_play"]["max_matchdays_per_player"] == 1

    async def test_otro_jugador_recibe_un_403(self, client: AsyncClient):
        _, creada = await self._stableford(client)
        await _usuario(client)

        respuesta = await client.patch(
            f"/api/v1/competitions/{creada['id']}/stroke-play", json={"category_limits": []}
        )

        assert respuesta.status_code == 403, respuesta.text

    async def test_una_competicion_que_no_existe_es_un_404(self, client: AsyncClient):
        await _usuario(client)

        respuesta = await client.patch(
            f"/api/v1/competitions/{uuid.uuid4()}/stroke-play", json={"category_limits": []}
        )

        assert respuesta.status_code == 404, respuesta.text

    async def test_a_una_ryder_es_un_400(self, client: AsyncClient):
        usuario = await _usuario(client)
        ryder = await create_competition(
            client, usuario["cookies"], _datos(tournament_type="RYDER_CUP")
        )

        respuesta = await client.patch(
            f"/api/v1/competitions/{ryder['id']}/stroke-play", json={"category_limits": []}
        )

        assert respuesta.status_code == 400, respuesta.text

    async def test_mas_jornadas_que_dias_es_un_400(self, client: AsyncClient):
        _, creada = await self._stableford(client)

        respuesta = await client.patch(
            f"/api/v1/competitions/{creada['id']}/stroke-play",
            json={"max_matchdays_per_player": 3},
        )

        assert respuesta.status_code == 400, respuesta.text
        assert "dura 2 días" in respuesta.json()["detail"]

    async def test_sin_sesion_es_un_401(self, client: AsyncClient):
        respuesta = await client.patch(
            f"/api/v1/competitions/{uuid.uuid4()}/stroke-play", json={"category_limits": []}
        )

        assert respuesta.status_code == 401, respuesta.text


async def test_acortar_el_torneo_por_debajo_de_las_jornadas_es_un_400(client: AsyncClient):
    usuario = await _usuario(client)
    creada = await create_competition(
        client, usuario["cookies"], _datos(stroke_play={"max_matchdays_per_player": 2})
    )

    respuesta = await client.put(
        f"/api/v1/competitions/{creada['id']}",
        json={"start_date": creada["start_date"], "end_date": creada["start_date"]},
    )

    assert respuesta.status_code == 400, respuesta.text
    assert "2 jornadas" in respuesta.json()["detail"]


async def test_un_limite_desmesurado_es_un_400_y_no_un_500(client: AsyncClient):
    """CodeRabbit, #501: redondearlo lanzaba InvalidOperation."""
    await _usuario(client)

    respuesta = await client.post(
        "/api/v1/competitions", json=_datos(stroke_play={"category_limits": ["1E+50"]})
    )

    assert respuesta.status_code == 400, respuesta.text
    assert "entre -10,0 y 54,0" in respuesta.json()["detail"]
