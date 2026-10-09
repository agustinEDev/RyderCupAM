"""
Generar las partidas de una franja por la API (#251, PR 4; decidido el 6-9 oct 2026).

| Caso                                          | Respuesta                                  |
|-----------------------------------------------|--------------------------------------------|
| El organizador, 4 jugadores, campo en Madrid  | 200: una partida a las 09:00, editable     |
| Otro jugador                                  | 403                                        |
| Inscripciones abiertas                        | 400 GROUPS_WINDOW_CLOSED                   |
| Una partida ya salió                          | 409 GROUP_ALREADY_STARTED                  |
| Campo sin coordenadas (sin zona horaria)      | 400 COURSE_WITHOUT_TIMEZONE                |
| Una jugadora y solo barras de hombre          | 400 PLAYERS_WITHOUT_TEE, con su color      |
| Uno solo                                      | 400 NOT_ENOUGH_PLAYERS                     |
| Franja que no existe / orden que no existe    | 404 / 422                                  |
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import (
    _URL_DE_LA_BD_DE_TEST,
    add_one_session,
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    create_golf_course,
    plaza_para_todos,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _sin_la_rfeg_de_verdad():
    """Los hándicaps son los manuales: la RFEG real limita a 429 en cuanto se le pregunta mucho."""
    from main import app
    from src.config.dependencies import get_handicap_service
    from src.modules.user.infrastructure.external.mock_handicap_service import (
        MockHandicapService,
    )

    app.dependency_overrides[get_handicap_service] = lambda: MockHandicapService(default=None)
    yield
    app.dependency_overrides.pop(get_handicap_service, None)


EN_MADRID = {"latitude": 40.4168, "longitude": -3.7038}


async def _usuario(client: AsyncClient, gender: str = "MALE", nombre: str = "Pa") -> dict:
    usuario = await create_authenticated_user(
        client,
        f"par-{uuid.uuid4().hex[:8]}@test.com",
        "P@ssw0rd123!",
        nombre,
        "Rtida",
        gender=gender,
    )
    set_auth_cookies(client, usuario["cookies"])
    respuesta = await client.post(
        "/api/v1/handicaps/update",
        json={"user_id": usuario["user"]["id"], "manual_handicap": 15.0},
    )
    assert respuesta.status_code == 200, respuesta.text
    return usuario


async def _franja_en_madrid(client: AsyncClient, organizador: dict, competicion: dict) -> str:
    """Una franja de 9:00 a 11:00 cada 10', de 4, en un campo con coordenadas (con zona)."""
    admin = await create_admin_user(
        client, f"admin-{uuid.uuid4()}@test.com", "P@ssw0rd123!", "Admin", "Partidas"
    )
    campo = await create_golf_course(
        client,
        organizador["cookies"],
        {
            "name": f"Campo partidas {uuid.uuid4().hex[:8]}",
            "country_code": "ES",
            "course_type": "STANDARD_18",
            "location": EN_MADRID,
            "tees": [
                {
                    "identifier": "Amarillo",
                    "color": "YELLOW",
                    "tee_gender": "MALE",
                    "course_rating": 70.2,
                    "slope_rating": 128,
                    "par": 72,
                }
            ],
            "holes": [{"hole_number": i, "par": 4, "stroke_index": i} for i in range(1, 19)],
        },
    )
    await approve_golf_course(client, admin["cookies"], campo["id"])
    set_auth_cookies(client, organizador["cookies"])
    anadido = await client.post(
        f"/api/v1/competitions/{competicion['id']}/golf-courses",
        json={"golf_course_id": campo["id"]},
    )
    assert anadido.status_code == 201, anadido.text
    franja = await client.post(
        f"/api/v1/competitions/{competicion['id']}/rounds",
        json={
            "golf_course_id": campo["id"],
            "round_date": competicion["start_date"],
            "session_type": "MORNING",
            "tee_sheet": {
                "first_tee_time": "09:00",
                "last_tee_time": "11:00",
                "interval_minutes": 10,
                "group_size": 4,
            },
        },
    )
    assert franja.status_code == 201, franja.text
    return franja.json()["id"]


async def _stableford(
    client: AsyncClient,
    jugadores: int = 3,
    con_zona: bool = True,
    cerrar: bool = True,
    generos: tuple[str, ...] = (),
) -> tuple[dict, dict, str, list[dict]]:
    """El organizador (inscrito) y `jugadores` más, todos con plaza en la franja."""
    organizador = await _usuario(client)
    start = date.today() + timedelta(days=30)
    competicion = await create_competition(
        client,
        organizador["cookies"],
        {
            "name": f"Par {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": start.isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "tournament_type": "STABLEFORD",
            "stroke_play": {"category_limits": [12.0]},
        },
    )
    if con_zona:
        franja = await _franja_en_madrid(client, organizador, competicion)
    else:
        franja = (await add_one_session(client, organizador["cookies"], competicion))["id"]
    otros = []
    for i in range(jugadores):
        jugador = await _usuario(client, gender=(generos[i] if i < len(generos) else "MALE"))
        set_auth_cookies(client, organizador["cookies"])
        directa = await client.post(
            f"/api/v1/competitions/{competicion['id']}/enrollments/direct",
            json={"competition_id": competicion["id"], "user_id": jugador["user"]["id"]},
        )
        assert directa.status_code in (200, 201), directa.text
        otros.append(jugador)
    await plaza_para_todos(client, organizador["cookies"], competicion)
    if cerrar:
        set_auth_cookies(client, organizador["cookies"])
        cerrada = await client.post(f"/api/v1/competitions/{competicion['id']}/close-enrollments")
        assert cerrada.status_code == 200, cerrada.text
    return organizador, competicion, franja, otros


async def _generar(client: AsyncClient, quien: dict, franja: str, order: str = "HIGH_FIRST"):
    set_auth_cookies(client, quien["cookies"])
    return await client.post(
        f"/api/v1/competitions/rounds/{franja}/groups/generate", json={"order": order}
    )


async def test_the_organiser_generates_them(client: AsyncClient):
    organizador, _, franja, _ = await _stableford(client)

    respuesta = await _generar(client, organizador, franja)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["round_id"] == franja
    assert cuerpo["editable"] is True
    assert cuerpo["unassigned_player_ids"] == []
    (partida,) = cuerpo["groups"]
    assert (partida["number"], partida["tee_time"], partida["status"]) == (1, "09:00", "SCHEDULED")
    assert partida["incomplete"] is False
    assert len(partida["players"]) == 4
    jugador = partida["players"][0]
    assert jugador["name"]
    assert jugador["handicap"] == "15.0"
    assert jugador["tee_color"] == "YELLOW"
    assert len(jugador["strokes_by_hole"]) == 18
    assert sum(jugador["strokes_by_hole"]) == jugador["playing_handicap"]
    marcados = {p["marks_user_id"] for p in partida["players"]}
    assert marcados == {p["user_id"] for p in partida["players"]}


async def test_another_player_cannot(client: AsyncClient):
    _, _, franja, jugadores = await _stableford(client)

    assert (await _generar(client, jugadores[0], franja)).status_code == 403


async def test_with_enrollments_open_it_is_out_of_time(client: AsyncClient):
    organizador, _, franja, _ = await _stableford(client, cerrar=False)

    respuesta = await _generar(client, organizador, franja)

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()["error_code"] == "GROUPS_WINDOW_CLOSED"


async def test_once_a_group_has_started(client: AsyncClient):
    organizador, _, franja, _ = await _stableford(client)
    assert (await _generar(client, organizador, franja)).status_code == 200
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE tee_groups SET status = 'IN_PROGRESS'"))
    finally:
        await engine.dispose()

    respuesta = await _generar(client, organizador, franja)

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["error_code"] == "GROUP_ALREADY_STARTED"


async def test_a_course_without_time_zone(client: AsyncClient):
    organizador, _, franja, _ = await _stableford(client, con_zona=False)

    respuesta = await _generar(client, organizador, franja)

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()["error_code"] == "COURSE_WITHOUT_TIMEZONE"


async def test_players_without_tees(client: AsyncClient):
    organizador, _, franja, jugadores = await _stableford(client, generos=("FEMALE",))

    respuesta = await _generar(client, organizador, franja)

    assert respuesta.status_code == 400, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "PLAYERS_WITHOUT_TEE"
    assert [(p["user_id"], p["missing"], p["tee_color"]) for p in cuerpo["players"]] == [
        (jugadores[0]["user"]["id"], "TEE_COLOR", "YELLOW")
    ]


async def test_one_player_alone(client: AsyncClient):
    organizador, _, franja, _ = await _stableford(client, jugadores=0)

    respuesta = await _generar(client, organizador, franja)

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()["error_code"] == "NOT_ENOUGH_PLAYERS"


async def test_a_window_that_does_not_exist(client: AsyncClient):
    organizador = await _usuario(client)

    assert (await _generar(client, organizador, str(uuid.uuid4()))).status_code == 404


async def test_an_order_that_does_not_exist(client: AsyncClient):
    organizador, _, franja, _ = await _stableford(client)

    assert (await _generar(client, organizador, franja, order="RANDOM")).status_code == 422


# ======================================================================================
# MOVER, REORDENAR, MARCADORES Y BORRAR
# ======================================================================================
#
# | Caso                                          | Respuesta                        |
# |-----------------------------------------------|----------------------------------|
# | Mover a una nueva al final                    | 200, la nueva incompleta         |
# | Mover a una llena sin intercambio             | 400 GROUP_FULL                   |
# | Mover, otro jugador                           | 403                              |
# | Reordenar / sin todas                         | 200 / 400 INVALID_GROUP_ORDER    |
# | Marcadores válidos / alguien a sí mismo       | 200 / 400 INVALID_MARKERS        |
# | Marcadores de una partida que no existe       | 404                              |
# | Borrar                                        | 204, la franja sin partidas      |


async def _generadas(client: AsyncClient, jugadores: int = 3) -> tuple[dict, str, list, list]:
    organizador, _, franja, otros = await _stableford(client, jugadores=jugadores)
    generadas = await _generar(client, organizador, franja)
    assert generadas.status_code == 200, generadas.text
    return organizador, franja, generadas.json()["groups"], otros


async def _mover(client, quien, franja, user_id, group_id=None, swap_with_user_id=None):
    set_auth_cookies(client, quien["cookies"])
    return await client.post(
        f"/api/v1/competitions/rounds/{franja}/groups/players",
        json={"user_id": user_id, "group_id": group_id, "swap_with_user_id": swap_with_user_id},
    )


async def _orden(client, quien, franja, group_ids):
    set_auth_cookies(client, quien["cookies"])
    return await client.put(
        f"/api/v1/competitions/rounds/{franja}/groups/order", json={"group_ids": group_ids}
    )


async def _marcadores(client, quien, group_id, markers):
    set_auth_cookies(client, quien["cookies"])
    return await client.put(
        f"/api/v1/competitions/groups/{group_id}/markers",
        json={"markers": [{"user_id": u, "marks_user_id": m} for u, m in markers]},
    )


async def test_moving_to_a_new_group_at_the_end(client: AsyncClient):
    organizador, franja, (partida,), _ = await _generadas(client)
    quien = partida["players"][0]["user_id"]

    respuesta = await _mover(client, organizador, franja, quien)

    assert respuesta.status_code == 200, respuesta.text
    grupos = respuesta.json()["groups"]
    assert [(g["tee_time"], g["incomplete"]) for g in grupos] == [
        ("09:00", False),
        ("09:10", True),
    ]
    assert grupos[1]["players"][0]["user_id"] == quien
    assert grupos[1]["players"][0]["marks_user_id"] is None


async def test_moving_to_a_full_group(client: AsyncClient):
    organizador, franja, (primera, segunda), _ = await _generadas(client, jugadores=7)

    respuesta = await _mover(
        client, organizador, franja, primera["players"][0]["user_id"], segunda["id"]
    )

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()["error_code"] == "GROUP_FULL"


async def test_another_player_cannot_move(client: AsyncClient):
    _, franja, (partida,), otros = await _generadas(client)

    respuesta = await _mover(client, otros[0], franja, partida["players"][0]["user_id"])

    assert respuesta.status_code == 403, respuesta.text


async def test_reordering(client: AsyncClient):
    organizador, franja, (primera, segunda), _ = await _generadas(client, jugadores=7)

    respuesta = await _orden(client, organizador, franja, [segunda["id"], primera["id"]])
    sin_todas = await _orden(client, organizador, franja, [segunda["id"]])

    assert respuesta.status_code == 200, respuesta.text
    assert [(g["id"], g["tee_time"]) for g in respuesta.json()["groups"]] == [
        (segunda["id"], "09:00"),
        (primera["id"], "09:10"),
    ]
    assert sin_todas.status_code == 400, sin_todas.text
    assert sin_todas.json()["error_code"] == "INVALID_GROUP_ORDER"


async def test_markers(client: AsyncClient):
    organizador, _, (partida,), _ = await _generadas(client)
    a, b, c, d = (p["user_id"] for p in partida["players"])

    parejas = await _marcadores(
        client, organizador, partida["id"], [(a, b), (b, a), (c, d), (d, c)]
    )
    a_si_mismo = await _marcadores(
        client, organizador, partida["id"], [(a, a), (b, c), (c, d), (d, b)]
    )
    sin_partida = await _marcadores(client, organizador, str(uuid.uuid4()), [])

    assert parejas.status_code == 200, parejas.text
    jugadores = parejas.json()["groups"][0]["players"]
    assert {p["user_id"]: p["marks_user_id"] for p in jugadores} == {a: b, b: a, c: d, d: c}
    assert a_si_mismo.status_code == 400, a_si_mismo.text
    assert a_si_mismo.json()["error_code"] == "INVALID_MARKERS"
    assert sin_partida.status_code == 404, sin_partida.text


async def test_deleting(client: AsyncClient):
    organizador, franja, _, _ = await _generadas(client)
    set_auth_cookies(client, organizador["cookies"])

    borradas = await client.delete(f"/api/v1/competitions/rounds/{franja}/groups")
    despues = await _orden(client, organizador, franja, [])

    assert borradas.status_code == 204, borradas.text
    assert despues.json()["groups"] == []
    assert len(despues.json()["unassigned_player_ids"]) == 4


async def test_swapping_with_one_of_a_full_group(client: AsyncClient):
    organizador, franja, (primera, segunda), _ = await _generadas(client, jugadores=7)
    a, x = primera["players"][0]["user_id"], segunda["players"][0]["user_id"]

    respuesta = await _mover(client, organizador, franja, a, segunda["id"], swap_with_user_id=x)

    assert respuesta.status_code == 200, respuesta.text
    primera, segunda = respuesta.json()["groups"]
    assert x in {p["user_id"] for p in primera["players"]}
    assert a in {p["user_id"] for p in segunda["players"]}
