"""
Anotar en las partidas de stroke play por la API (#251, PR 5).

| Caso                                        | Respuesta                                  |
|---------------------------------------------|--------------------------------------------|
| Antes de la primera salida                  | 409 SCORING_NOT_OPEN_YET + scoring_opens_at|
| Su golpe y el de su marcado                 | 200 con la vista                           |
| Marcando a otro                             | 403 NOT_YOUR_MARKED_PLAYER                 |
| Quien no juega la partida                   | 403 NOT_GROUP_PLAYER                       |
| Hoyo 19                                     | 400 INVALID_HOLE                           |
| Levantar bola en Medal                      | 400 PICKED_UP_NOT_ALLOWED                  |
| La vista, de una que no existe              | 200 / 404                                  |
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import set_auth_cookies
from tests.integration.api.v1.test_tee_groups_endpoints import (  # noqa: F401
    _generar,
    _sin_la_rfeg_de_verdad,
    _stableford,
    _usuario,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def _ya_abrio():
    """El reloj del servidor, a mediodía del día del torneo (la franja sale a las 9)."""
    from main import app
    from src.config.dependencies import get_reloj_del_servidor

    dia = date.today() + timedelta(days=30)
    app.dependency_overrides[get_reloj_del_servidor] = lambda: (
        lambda: datetime(dia.year, dia.month, dia.day, 12, 0, tzinfo=UTC)
    )
    yield
    app.dependency_overrides.pop(get_reloj_del_servidor, None)


async def _con_partida(client: AsyncClient, tipo: str = "STABLEFORD"):
    organizador, _, franja, otros = await _stableford(client, tipo=tipo)
    generadas = await _generar(client, organizador, franja)
    assert generadas.status_code == 200, generadas.text
    (partida,) = generadas.json()["groups"]
    por_id = {o["user"]["id"]: o for o in [organizador, *otros]}
    return partida, por_id


async def _anotar(client, quien, partida, hoyo=1, **body):
    set_auth_cookies(client, quien["cookies"])
    return await client.post(
        f"/api/v1/competitions/groups/{partida['id']}/scores/holes/{hoyo}", json=body
    )


def _marca_a(partida, user_id):
    return next(p["marks_user_id"] for p in partida["players"] if p["user_id"] == user_id)


async def test_before_the_first_tee_time(client: AsyncClient):
    partida, por_id = await _con_partida(client)
    yo = partida["players"][0]["user_id"]

    respuesta = await _anotar(
        client, por_id[yo], partida, own_score=4, marked_player_id=_marca_a(partida, yo)
    )

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["error_code"] == "SCORING_NOT_OPEN_YET"
    assert respuesta.json()["scoring_opens_at"]


@pytest.mark.usefixtures("_ya_abrio")
async def test_own_and_marked_score(client: AsyncClient):
    partida, por_id = await _con_partida(client)
    yo = partida["players"][0]["user_id"]
    marcado = _marca_a(partida, yo)

    respuesta = await _anotar(
        client, por_id[yo], partida, own_score=4, marked_player_id=marcado, marked_score=5
    )

    assert respuesta.status_code == 200, respuesta.text
    vista = respuesta.json()
    assert vista["status"] == "IN_PROGRESS"
    assert vista["i_mark_user_id"] == marcado
    jugadores = {p["user_id"]: p for p in vista["players"]}
    assert jugadores[yo]["holes"][0]["own_score"] == 4
    assert jugadores[marcado]["holes"][0]["marker_score"] == 5


@pytest.mark.usefixtures("_ya_abrio")
async def test_marking_someone_else(client: AsyncClient):
    partida, por_id = await _con_partida(client)
    yo = partida["players"][0]["user_id"]
    otro = next(
        p["user_id"] for p in partida["players"] if p["user_id"] not in (yo, _marca_a(partida, yo))
    )

    respuesta = await _anotar(
        client, por_id[yo], partida, own_score=4, marked_player_id=otro, marked_score=5
    )

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["error_code"] == "NOT_YOUR_MARKED_PLAYER"


@pytest.mark.usefixtures("_ya_abrio")
async def test_someone_not_in_the_group(client: AsyncClient):
    partida, _ = await _con_partida(client)
    ajeno = await _usuario(client)

    respuesta = await _anotar(
        client, ajeno, partida, own_score=4, marked_player_id=ajeno["user"]["id"]
    )

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()["error_code"] == "NOT_GROUP_PLAYER"


@pytest.mark.usefixtures("_ya_abrio")
async def test_hole_nineteen(client: AsyncClient):
    partida, por_id = await _con_partida(client)
    yo = partida["players"][0]["user_id"]

    respuesta = await _anotar(
        client, por_id[yo], partida, hoyo=19, own_score=4, marked_player_id=_marca_a(partida, yo)
    )

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()["error_code"] == "INVALID_HOLE"


@pytest.mark.usefixtures("_ya_abrio")
async def test_picking_up_in_medal(client: AsyncClient):
    partida, por_id = await _con_partida(client, tipo="MEDAL")
    yo = partida["players"][0]["user_id"]

    respuesta = await _anotar(
        client, por_id[yo], partida, own_score=None, marked_player_id=_marca_a(partida, yo)
    )

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()["error_code"] == "PICKED_UP_NOT_ALLOWED"


async def test_the_view(client: AsyncClient):
    partida, por_id = await _con_partida(client)
    yo = partida["players"][0]["user_id"]
    set_auth_cookies(client, por_id[yo]["cookies"])

    vista = await client.get(f"/api/v1/competitions/groups/{partida['id']}/scoring-view")
    no_existe = await client.get(f"/api/v1/competitions/groups/{uuid.uuid4()}/scoring-view")

    assert vista.status_code == 200, vista.text
    assert len(vista.json()["players"]) == 4
    assert no_existe.status_code == 404, no_existe.text


# | Entregar / retirarse                        | Respuesta                                  |
# |---------------------------------------------|--------------------------------------------|
# | Sin empezar                                 | 409 GROUP_NOT_STARTED                      |
# | Con hoyos sin validar                       | 400 SCORECARD_NOT_READY con `holes`        |
# | Retirarse                                   | 200, su tarjeta RETIRADO                   |


async def _post(client, quien, partida, ruta):
    set_auth_cookies(client, quien["cookies"])
    return await client.post(f"/api/v1/competitions/groups/{partida['id']}/scorecard{ruta}")


async def test_delivering_before_the_group_started(client: AsyncClient):
    partida, por_id = await _con_partida(client)
    yo = partida["players"][0]["user_id"]

    respuesta = await _post(client, por_id[yo], partida, "")

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["error_code"] == "GROUP_NOT_STARTED"


@pytest.mark.usefixtures("_ya_abrio")
async def test_delivering_with_holes_not_validated(client: AsyncClient):
    partida, por_id = await _con_partida(client)
    yo = partida["players"][0]["user_id"]
    await _anotar(client, por_id[yo], partida, own_score=4, marked_player_id=_marca_a(partida, yo))

    respuesta = await _post(client, por_id[yo], partida, "")

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()["error_code"] == "SCORECARD_NOT_READY"
    assert respuesta.json()["holes"] == list(range(1, 19))


@pytest.mark.usefixtures("_ya_abrio")
async def test_retiring(client: AsyncClient):
    partida, por_id = await _con_partida(client)
    yo = partida["players"][0]["user_id"]
    await _anotar(client, por_id[yo], partida, own_score=4, marked_player_id=_marca_a(partida, yo))

    respuesta = await _post(client, por_id[yo], partida, "/retire")

    assert respuesta.status_code == 200, respuesta.text
    jugadores = {p["user_id"]: p for p in respuesta.json()["players"]}
    assert jugadores[yo]["card_status"] == "RETIRADO"
