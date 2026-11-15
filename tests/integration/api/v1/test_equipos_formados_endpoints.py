"""
Con los equipos formados, quedan así: los 409 por HTTP (decidido el 29 oct 2026).

La regla está en unitarios (test_equipos_formados_congelados); aquí, que cada
ruta da su 409 con `error_code` en la raíz, para que la pantalla lo diga en su
idioma, y que el organizador sigue pudiendo quitar a alguien y reiniciarlo.
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
    inscrito_por_invitacion,
    set_auth_cookies,
    solicitud_pendiente,
)

pytestmark = pytest.mark.asyncio


async def _con_equipos(client: AsyncClient, invitar: dict | None = None) -> dict:
    """Una pública con el creador y tres inscritos, capitanes y equipos al azar."""
    creador = await create_authenticated_user(
        client, "congelados-org@test.com", "P@ssw0rd123!", "Org", "Congelados"
    )
    jugadores = [
        await create_authenticated_user(
            client, f"congelados-{i}@test.com", "P@ssw0rd123!", "Jugador" + "ABC"[i], "Congelados"
        )
        for i in range(3)
    ]
    comp = await create_competition(client, creador["cookies"])
    set_auth_cookies(client, creador["cookies"])
    for jugador in jugadores:
        inscrito = await inscrito_por_invitacion(client, creador["cookies"], comp["id"], jugador)
        jugador["enrollment_id"] = inscrito["enrollment_id"]
    invitacion = None
    if invitar is not None:
        enviada = await client.post(
            f"/api/v1/competitions/{comp['id']}/invitations",
            json={"invitee_user_id": invitar["user"]["id"]},
        )
        assert enviada.status_code == 201, enviada.text
        invitacion = enviada.json()["id"]
    # Nombrarlos cierra las inscripciones
    nombrados = await client.put(
        f"/api/v1/competitions/{comp['id']}/captains",
        json={
            "team_a_captain_id": creador["user"]["id"],
            "team_b_captain_id": jugadores[0]["user"]["id"],
        },
    )
    assert nombrados.status_code == 200, nombrados.text
    repartidos = await _formar(client, comp)
    assert repartidos.status_code == 201, repartidos.text
    return {"comp": comp, "creador": creador, "jugadores": jugadores, "invitacion": invitacion}


async def _formar(client: AsyncClient, comp: dict):
    return await client.post(
        f"/api/v1/competitions/{comp['id']}/teams",
        json={"competition_id": comp["id"], "mode": "AUTOMATIC"},
    )


async def _reabrir(client: AsyncClient, montaje: dict) -> None:
    set_auth_cookies(client, montaje["creador"]["cookies"])
    reabierta = await client.post(
        f"/api/v1/competitions/{montaje['comp']['id']}/reopen-enrollments"
    )
    assert reabierta.status_code == 200, reabierta.text


def _es_teams_formed(respuesta) -> None:
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["error_code"] == "TEAMS_FORMED"


async def test_j1_el_jugador_no_se_retira(client: AsyncClient):
    montaje = await _con_equipos(client)
    jugador = montaje["jugadores"][1]
    set_auth_cookies(client, jugador["cookies"])

    baja = await client.post(f"/api/v1/enrollments/{jugador['enrollment_id']}/withdraw", json={})

    _es_teams_formed(baja)


async def test_j2_nadie_se_inscribe_en_la_publica_reabierta(client: AsyncClient):
    montaje = await _con_equipos(client)
    await _reabrir(client, montaje)
    nuevo = await create_authenticated_user(
        client, "congelados-nuevo@test.com", "P@ssw0rd123!", "Nuevo", "Congelados"
    )
    set_auth_cookies(client, nuevo["cookies"])

    pedida = await client.post(f"/api/v1/competitions/{montaje['comp']['id']}/enrollments")

    _es_teams_formed(pedida)


async def test_j4_aceptar_sin_partidos_entra_y_se_reinician(client: AsyncClient):
    """
    B-02, P2 (15 nov 2026). Given una invitación enviada antes de nombrar capitanes,
    que sigue pendiente (cerrar ya no las rechaza), y los equipos formados sin
    partidos / When la acepta / Then entra y los equipos se reinician; los
    capitanes se quedan, como al quitar a alguien.
    """
    invitado = await create_authenticated_user(
        client, "congelados-invitado@test.com", "P@ssw0rd123!", "Invitado", "Congelados"
    )
    montaje = await _con_equipos(client, invitar=invitado)
    set_auth_cookies(client, invitado["cookies"])

    aceptada = await client.post(
        f"/api/v1/invitations/{montaje['invitacion']}/respond", json={"action": "ACCEPT"}
    )

    assert aceptada.status_code == 200, aceptada.text
    assert aceptada.json()["status"] == "ACCEPTED"
    set_auth_cookies(client, montaje["creador"]["cookies"])
    ficha = (await client.get(f"/api/v1/competitions/{montaje['comp']['id']}")).json()
    assert ficha["status"] == "CLOSED"
    assert ficha["teams_assigned"] is False
    assert ficha["team_b_captain_id"] == montaje["jugadores"][0]["user"]["id"]


async def test_o4_no_se_vuelven_a_formar(client: AsyncClient):
    montaje = await _con_equipos(client)
    set_auth_cookies(client, montaje["creador"]["cookies"])

    otra_vez = await _formar(client, montaje["comp"])

    _es_teams_formed(otra_vez)


async def test_o1_el_organizador_le_quita_y_se_reinicia(client: AsyncClient):
    """Volver a formarlos tras el reinicio está en unitarios (O6): aquí quedan impares."""
    montaje = await _con_equipos(client)
    set_auth_cookies(client, montaje["creador"]["cookies"])
    quitado = montaje["jugadores"][2]

    quitar = await client.post(f"/api/v1/enrollments/{quitado['enrollment_id']}/remove")
    ficha = await client.get(f"/api/v1/competitions/{montaje['comp']['id']}")

    assert quitar.status_code == 200, quitar.text
    assert ficha.json()["teams_assigned"] is False
    # Los capitanes se quedan
    assert ficha.json()["team_b_captain_id"] == montaje["jugadores"][0]["user"]["id"]


async def test_i1_con_equipos_no_se_invita_por_id(client: AsyncClient):
    montaje = await _con_equipos(client)
    await _reabrir(client, montaje)
    invitado = await create_authenticated_user(
        client, "congelados-inv-id@test.com", "P@ssw0rd123!", "Invitado", "Congelados"
    )
    set_auth_cookies(client, montaje["creador"]["cookies"])

    invitacion = await client.post(
        f"/api/v1/competitions/{montaje['comp']['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )

    _es_teams_formed(invitacion)


async def test_i2_con_equipos_no_se_invita_por_email(client: AsyncClient):
    montaje = await _con_equipos(client)
    await _reabrir(client, montaje)

    invitacion = await client.post(
        f"/api/v1/competitions/{montaje['comp']['id']}/invitations/by-email",
        json={"invitee_email": "congelados-nadie@example.com"},
    )

    _es_teams_formed(invitacion)


async def _con_partidos(client: AsyncClient) -> dict:
    """Dos contra dos con los individuales generados, una solicitud sin aprobar, una
    invitación pendiente y reabierta."""
    creador = await create_authenticated_user(
        client, "cp-org@test.com", "P@ssw0rd123!", "Org", "Partidos"
    )
    jugadores = [
        await create_authenticated_user(
            client, f"cp-{i}@test.com", "P@ssw0rd123!", "Jugador" + "ABCDE"[i], "Partidos"
        )
        for i in range(5)
    ]
    admin = await create_admin_user(
        client, "cp-admin@test.com", "P@ssw0rd123!", "Admin", "Partidos"
    )
    inicio = date.today() + timedelta(days=30)
    comp = await create_competition(
        client,
        creador["cookies"],
        {
            "name": "Congelados con partidos",
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
    # Tres entran invitados; el cuarto tiene una solicitud sin aprobar, y el
    # quinto una invitación pendiente (cerrar ya no la rechaza, B-02)
    for jugador in jugadores[:3]:
        await inscrito_por_invitacion(client, creador["cookies"], comp_id, jugador)
    respuesta = await client.post(
        f"/api/v1/competitions/{comp_id}/invitations",
        json={"invitee_user_id": jugadores[4]["user"]["id"]},
    )
    assert respuesta.status_code == 201, respuesta.text
    invitacion = respuesta.json()["id"]
    # Desde el 28 oct las públicas no crean solicitudes: una de antes
    set_auth_cookies(client, jugadores[3]["cookies"])
    pedida = await solicitud_pendiente(client, comp_id)
    set_auth_cookies(client, creador["cookies"])
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
            "team_a_player_ids": [creador["user"]["id"], jugadores[0]["user"]["id"]],
            "team_b_player_ids": [jugadores[1]["user"]["id"], jugadores[2]["user"]["id"]],
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    respuesta = await client.post(
        f"/api/v1/competitions/rounds/{round_id}/matches/generate", json={}
    )
    assert respuesta.status_code in (200, 201), respuesta.text
    respuesta = await client.post(f"/api/v1/competitions/{comp_id}/reopen-enrollments")
    assert respuesta.status_code == 200, respuesta.text
    return {
        "comp_id": comp_id,
        "pedida": pedida["id"],
        "creador": creador,
        "invitado": jugadores[4],
        "invitacion": invitacion,
    }


async def test_e1_con_partidos_no_se_acepta_y_sigue_pendiente(client: AsyncClient):
    """B-02, P2: con partidos, aceptar es 409 TEAMS_FORMED y la invitación sigue pendiente."""
    montaje = await _con_partidos(client)
    set_auth_cookies(client, montaje["invitado"]["cookies"])

    aceptada = await client.post(
        f"/api/v1/invitations/{montaje['invitacion']}/respond", json={"action": "ACCEPT"}
    )

    _es_teams_formed(aceptada)
    mias = (await client.get("/api/v1/invitations/me")).json()["invitations"]
    assert [i["status"] for i in mias] == ["PENDING"]


async def test_e3_con_partidos_no_se_aprueba(client: AsyncClient):
    montaje = await _con_partidos(client)
    set_auth_cookies(client, montaje["creador"]["cookies"])

    aprobada = await client.post(f"/api/v1/enrollments/{montaje['pedida']}/approve")

    _es_teams_formed(aprobada)
