"""
Reasignar rivales de la Ryder en dos pasos, de punta a punta (22 oct 2026).

Dos `PUT matches/{id}/players`: entre los dos, quien se queda sin partido pierde
su aviso de salida, y en el segundo le vuelve a nacer uno. Debe decir «te han
cambiado» (`changed: true`), no «ya tienes partido». Cubre el cableado real:
la tabla de avisos retirados en Postgres y el candado del torneo.
"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    activate_competition,
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    create_golf_course,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio
PASSWORD = "P@ssw0rd123!"


async def _ryder_de_dos_partidos(client: AsyncClient) -> tuple[dict, dict, list[dict]]:
    """Dos individuales generados: A1 y A2 contra B1 y B2. Devuelve (creador, jugadores, partidos)."""
    creador = await create_authenticated_user(client, "r2p_c@test.com", PASSWORD, "Creador", "Dos")
    nombres = {"a1": "Ana", "a2": "Alba", "b1": "Bea", "b2": "Berta"}
    jugadores = {
        clave: await create_authenticated_user(
            client, f"r2p_{clave}@test.com", PASSWORD, nombre, "Dos"
        )
        for clave, nombre in nombres.items()
    }
    admin = await create_admin_user(client, "r2p_admin@test.com", PASSWORD, "Admin", "Dos")
    inicio = date.today() + timedelta(days=30)
    comp = await create_competition(
        client,
        creador["cookies"],
        {
            "name": "Ryder en dos pasos",
            "start_date": inicio.isoformat(),
            "end_date": (inicio + timedelta(days=3)).isoformat(),
            "main_country": "ES",
            "play_mode": "SCRATCH",
            "max_players": 24,
            "team_assignment": "MANUAL",
            "visibility": "PUBLIC",
        },
    )
    comp_id = comp["id"]
    campo = await create_golf_course(client, creador["cookies"])
    await approve_golf_course(client, admin["cookies"], campo["id"])
    set_auth_cookies(client, creador["cookies"])
    respuesta = await client.post(
        f"/api/v1/competitions/{comp_id}/golf-courses", json={"golf_course_id": campo["id"]}
    )
    assert respuesta.status_code == 201, respuesta.text
    await activate_competition(client, creador["cookies"], comp_id)

    for jugador in jugadores.values():
        set_auth_cookies(client, jugador["cookies"])
        respuesta = await client.post(f"/api/v1/competitions/{comp_id}/enrollments")
        assert respuesta.status_code in (200, 201), respuesta.text
    set_auth_cookies(client, creador["cookies"])
    for inscripcion in (await client.get(f"/api/v1/competitions/{comp_id}/enrollments")).json():
        if inscripcion["status"] == "REQUESTED":
            respuesta = await client.post(f"/api/v1/enrollments/{inscripcion['id']}/approve")
            assert respuesta.status_code == 200, respuesta.text
    for inscripcion in (await client.get(f"/api/v1/competitions/{comp_id}/enrollments")).json():
        if inscripcion["user_id"] == creador["user"]["id"] and inscripcion["status"] == "APPROVED":
            respuesta = await client.post(f"/api/v1/enrollments/{inscripcion['id']}/withdraw")
            assert respuesta.status_code == 200, respuesta.text
    respuesta = await client.post(f"/api/v1/competitions/{comp_id}/close-enrollments")
    assert respuesta.status_code == 200, respuesta.text

    respuesta = await client.post(
        f"/api/v1/competitions/{comp_id}/rounds",
        json={
            "golf_course_id": campo["id"],
            "round_date": inicio.isoformat(),
            "session_type": "MORNING",
            "match_format": "SINGLES",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    round_id = respuesta.json()["id"]
    respuesta = await client.post(
        f"/api/v1/competitions/{comp_id}/teams",
        json={
            "mode": "MANUAL",
            "team_a_player_ids": [jugadores[k]["user"]["id"] for k in ("a1", "a2")],
            "team_b_player_ids": [jugadores[k]["user"]["id"] for k in ("b1", "b2")],
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    respuesta = await client.post(
        f"/api/v1/competitions/rounds/{round_id}/matches/generate", json={}
    )
    assert respuesta.status_code == 201, respuesta.text

    agenda = (await client.get(f"/api/v1/competitions/{comp_id}/schedule")).json()
    partidos = agenda["days"][0]["rounds"][0]["matches"]
    assert len(partidos) == 2
    return creador, jugadores, partidos


def _ids(partido: dict, lado: str) -> list[str]:
    return [p["user_id"] for p in partido[f"{lado}_players"]]


async def _aviso_de(client: AsyncClient, jugador: dict) -> list[dict]:
    set_auth_cookies(client, jugador["cookies"])
    respuesta = await client.get("/api/v1/users/me/feed")
    assert respuesta.status_code == 200, respuesta.text
    return [e for e in respuesta.json()["events"] if e["type"] == "TEE_TIME_ASSIGNED"]


async def test_who_was_left_without_a_match_gets_a_changed_notice(client: AsyncClient):
    creador, jugadores, (m1, m2) = await _ryder_de_dos_partidos(client)
    a_de_m1, (b_de_m1,) = _ids(m1, "team_a"), _ids(m1, "team_b")
    a_de_m2, (b_de_m2,) = _ids(m2, "team_a"), _ids(m2, "team_b")
    sin_partido = next(j for j in jugadores.values() if j["user"]["id"] == b_de_m1)
    (antes,) = await _aviso_de(client, sin_partido)
    assert antes["payload"]["changed"] is False

    # Paso 1: m1 pasa a jugar contra el B de m2; el B de m1 se queda sin partido
    set_auth_cookies(client, creador["cookies"])
    respuesta = await client.put(
        f"/api/v1/competitions/matches/{m1['id']}/players",
        json={"team_a_player_ids": a_de_m1, "team_b_player_ids": [b_de_m2]},
    )
    assert respuesta.status_code == 200, respuesta.text
    assert await _aviso_de(client, sin_partido) == []

    # Paso 2: m2 juega contra el que se quedo sin partido
    set_auth_cookies(client, creador["cookies"])
    respuesta = await client.put(
        f"/api/v1/competitions/matches/{m2['id']}/players",
        json={"team_a_player_ids": a_de_m2, "team_b_player_ids": [b_de_m1]},
    )
    assert respuesta.status_code == 200, respuesta.text

    (despues,) = await _aviso_de(client, sin_partido)
    assert despues["payload"]["changed"] is True
    assert despues["payload"]["opponent_ids"] == a_de_m2


async def _anotaciones_de_la_ronda(round_id: str, apuntar: tuple[str, str] | None = None) -> int:
    """Cuantas anotaciones de avisos retirados tiene la ronda; antes apunta una si se pide."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.conftest import _URL_DE_LA_BD_DE_TEST

    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            if apuntar is not None:
                user_id, competition_id = apuntar
                await conn.execute(
                    text(
                        "INSERT INTO withdrawn_tee_time_notices (user_id, round_id, competition_id)"
                        " VALUES (:u, :r, :c)"
                    ),
                    {"u": user_id, "r": round_id, "c": competition_id},
                )
            fila = await conn.execute(
                text("SELECT count(*) FROM withdrawn_tee_time_notices WHERE round_id = :r"),
                {"r": round_id},
            )
            return int(fila.scalar_one())
    finally:
        await engine.dispose()


async def test_deleting_the_round_forgets_its_withdrawn_notices(client: AsyncClient):
    """Revisor sin contexto (22 oct): borrar la ronda no deja anotaciones huerfanas."""
    from tests.integration.api.v1.test_generate_matches_block import _fourball_de_uno_contra_uno

    montaje = await _fourball_de_uno_contra_uno(client)
    round_id = montaje["round_id"]
    creador = montaje["creador"]
    assert (
        await _anotaciones_de_la_ronda(round_id, (creador["user"]["id"], montaje["comp_id"])) == 1
    )

    set_auth_cookies(client, creador["cookies"])
    respuesta = await client.delete(f"/api/v1/competitions/rounds/{round_id}")
    assert respuesta.status_code == 200, respuesta.text

    assert await _anotaciones_de_la_ronda(round_id) == 0
