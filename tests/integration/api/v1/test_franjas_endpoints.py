"""
Las franjas de un Stableford o un Medal, por la API (#251, decidido el 6-7 oct 2026).
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    add_one_session,
    approve_golf_course,
    create_admin_user,
    create_authenticated_user,
    create_competition,
    create_golf_course,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio

HOJA = {
    "first_tee_time": "09:00",
    "last_tee_time": "09:20",
    "interval_minutes": 10,
    "group_size": 4,
}


async def _organizador(client: AsyncClient) -> dict:
    usuario = await create_authenticated_user(
        client, f"fr-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Fran", "Ja"
    )
    set_auth_cookies(client, usuario["cookies"])
    respuesta = await client.post(
        "/api/v1/handicaps/update",
        json={"user_id": usuario["user"]["id"], "manual_handicap": 15.0},
    )
    assert respuesta.status_code == 200, respuesta.text
    return usuario


async def _torneo(client: AsyncClient, tipo="STABLEFORD") -> tuple[dict, dict]:
    usuario = await _organizador(client)
    start = date.today() + timedelta(days=30)
    datos = {
        "name": f"Medal {uuid.uuid4().hex[:8]}",
        "start_date": start.isoformat(),
        "end_date": start.isoformat(),
        "main_country": "ES",
        "play_mode": "HANDICAP",
        "tournament_type": tipo,
    }
    if tipo != "RYDER_CUP":
        datos["stroke_play"] = {"category_limits": [12.0]}
    competicion = await create_competition(client, usuario["cookies"], datos)
    return usuario, competicion


async def test_crear_una_franja_y_verla_en_el_calendario_con_su_cupo(client: AsyncClient):
    usuario, competicion = await _torneo(client)
    franja = await add_one_session(client, usuario["cookies"], competicion)

    calendario = await client.get(f"/api/v1/competitions/{competicion['id']}/schedule")

    assert calendario.status_code == 200, calendario.text
    cuerpo = calendario.json()
    (sesion,) = cuerpo["days"][0]["rounds"]
    assert sesion["id"] == franja["id"]
    assert sesion["tee_sheet"]["capacity"] == 52  # 9:00 a 11:00 cada 10, de 4
    assert len(sesion["tee_sheet"]["tee_times"]) == 13
    assert sesion["match_format"] == "SINGLES"
    assert sesion["effective_allowance"] == 95
    assert cuerpo["tee_sheet_capacity"] == 52


async def test_una_franja_solapada_o_sin_hoja_es_un_400(client: AsyncClient):
    usuario, competicion = await _torneo(client)
    await add_one_session(client, usuario["cookies"], competicion)
    set_auth_cookies(client, usuario["cookies"])
    calendario = (await client.get(f"/api/v1/competitions/{competicion['id']}/schedule")).json()
    base = {
        "golf_course_id": calendario["days"][0]["rounds"][0]["golf_course_id"],
        "round_date": competicion["start_date"],
        "session_type": "AFTERNOON",
    }

    solapada = await client.post(
        f"/api/v1/competitions/{competicion['id']}/rounds",
        json={**base, "tee_sheet": {**HOJA, "first_tee_time": "10:30", "last_tee_time": "12:00"}},
    )
    sin_hoja = await client.post(
        f"/api/v1/competitions/{competicion['id']}/rounds",
        json={**base, "session_type": "EVENING"},
    )

    assert solapada.status_code == 400, solapada.text
    assert "MORNING" in solapada.json()["detail"]
    assert sin_hoja.status_code == 400, sin_hoja.text


async def test_cambiar_la_hoja_de_una_franja(client: AsyncClient):
    usuario, competicion = await _torneo(client)
    franja = await add_one_session(client, usuario["cookies"], competicion)
    set_auth_cookies(client, usuario["cookies"])

    cambio = await client.put(
        f"/api/v1/competitions/rounds/{franja['id']}",
        json={"tee_sheet": {**HOJA, "group_size": 3}},
    )
    calendario = (await client.get(f"/api/v1/competitions/{competicion['id']}/schedule")).json()

    assert cambio.status_code == 200, cambio.text
    assert calendario["days"][0]["rounds"][0]["tee_sheet"]["capacity"] == 9


async def test_en_una_ryder_la_hoja_es_un_400_y_el_calendario_no_da_cupo(client: AsyncClient):
    usuario, competicion = await _torneo(client, "RYDER_CUP")
    admin = await create_admin_user(
        client, f"adm-{uuid.uuid4().hex[:8]}@test.com", "P@ssw0rd123!", "Ad", "Min"
    )
    campo = await create_golf_course(client, usuario["cookies"])
    await approve_golf_course(client, admin["cookies"], campo["id"])
    set_auth_cookies(client, usuario["cookies"])
    await client.post(
        f"/api/v1/competitions/{competicion['id']}/golf-courses",
        json={"golf_course_id": campo["id"]},
    )

    con_hoja = await client.post(
        f"/api/v1/competitions/{competicion['id']}/rounds",
        json={
            "golf_course_id": campo["id"],
            "round_date": competicion["start_date"],
            "session_type": "MORNING",
            "match_format": "SINGLES",
            "tee_sheet": HOJA,
        },
    )
    calendario = (await client.get(f"/api/v1/competitions/{competicion['id']}/schedule")).json()

    assert con_hoja.status_code == 400, con_hoja.text
    assert calendario["tee_sheet_capacity"] is None


async def test_una_hora_con_segundos_o_huso_es_un_400(client: AsyncClient):
    usuario, competicion = await _torneo(client)
    await add_one_session(client, usuario["cookies"], competicion)
    set_auth_cookies(client, usuario["cookies"])
    calendario = (await client.get(f"/api/v1/competitions/{competicion['id']}/schedule")).json()
    base = {
        "golf_course_id": calendario["days"][0]["rounds"][0]["golf_course_id"],
        "round_date": competicion["start_date"],
        "session_type": "AFTERNOON",
    }

    respuestas = [
        await client.post(
            f"/api/v1/competitions/{competicion['id']}/rounds",
            json={**base, "tee_sheet": {**HOJA, "first_tee_time": hora, "last_tee_time": "17:00"}},
        )
        for hora in ("15:00:30", "15:00Z")
    ]

    assert [r.status_code for r in respuestas] == [400, 400], [r.text for r in respuestas]
