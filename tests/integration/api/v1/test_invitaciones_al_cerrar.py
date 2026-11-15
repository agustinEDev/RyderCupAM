"""
Las invitaciones pendientes al cerrar la inscripción, por la API (Agustín, 15 nov 2026).

Hasta el 15 nov (#710) cerrar las dejaba sin plaza. Ahora esperan (ON_HOLD, «En
lista de espera»: no es la lista de espera de las franjas):

| Caso | Situación                                          | Qué se ve por la API                      |
|------|----------------------------------------------------|-------------------------------------------|
| P1   | se cierra con una pendiente                        | ON_HOLD en «mis invitaciones»; aceptarla: |
|      |                                                    | 409 INVITATION_ON_HOLD con el texto       |
|      |                                                    | aprobado; la ya contestada, igual         |
| P1   | el invitado la rechaza, o el organizador la retira | DECLINED / 204 y CANCELLED                |
| P1   | cerrada, el organizador invita a otro              | 422, como siempre (C2: no se invita)      |
| P2   | el organizador reabre                              | PENDING, «ya puedes aceptar», se acepta   |
| P3   | empieza o se cancela sin reabrir                   | NO_ROOM                                   |
| P3   | se cancela con la inscripción abierta              | las PENDING, NO_ROOM y «no hubo plaza»    |
| B3   | equipos sin partidos: el invitado acepta           | el organizador ve TEAMS_UNDONE_BY_ENTRY   |
"""

import pytest
from httpx import AsyncClient

from tests.conftest import (
    add_one_session,
    create_authenticated_user,
    create_competition,
    inscrito_por_invitacion,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio

EN_ESPERA = "En lista de espera: la inscripción está cerrada. Si el organizador la reabre, podrás aceptarla."


async def _invitado_y_cerrada(client: AsyncClient) -> dict:
    creador = await create_authenticated_user(
        client, "ic_creator@test.com", "P@ssw0rd123!", "Creator", "Cierre"
    )
    invitado = await create_authenticated_user(
        client, "ic_invitee@test.com", "P@ssw0rd123!", "Invitee", "Cierre"
    )
    ya_dijo_que_no = await create_authenticated_user(
        client, "ic_declined@test.com", "P@ssw0rd123!", "Declined", "Cierre"
    )
    comp = await create_competition(client, creador["cookies"])
    for jugador in (invitado, ya_dijo_que_no):
        set_auth_cookies(client, creador["cookies"])
        respuesta = await client.post(
            f"/api/v1/competitions/{comp['id']}/invitations",
            json={"invitee_user_id": jugador["user"]["id"]},
        )
        assert respuesta.status_code == 201, respuesta.text
    # Una ya contestada: el cierre solo toca las pendientes
    set_auth_cookies(client, ya_dijo_que_no["cookies"])
    suya = (await client.get("/api/v1/invitations/me")).json()["invitations"][0]
    respuesta = await client.post(
        f"/api/v1/invitations/{suya['id']}/respond", json={"action": "DECLINE"}
    )
    assert respuesta.status_code == 200, respuesta.text
    set_auth_cookies(client, creador["cookies"])
    respuesta = await client.post(f"/api/v1/competitions/{comp['id']}/close-enrollments")
    assert respuesta.status_code == 200, respuesta.text
    return {
        "creador": creador,
        "invitado": invitado,
        "ya_dijo_que_no": ya_dijo_que_no,
        "comp": comp,
    }


async def _la_suya(client: AsyncClient, montaje: dict) -> dict:
    set_auth_cookies(client, montaje["invitado"]["cookies"])
    return (await client.get("/api/v1/invitations/me")).json()["invitations"][0]


async def _inscritos(client: AsyncClient, montaje: dict) -> list[str]:
    set_auth_cookies(client, montaje["creador"]["cookies"])
    respuesta = await client.get(f"/api/v1/competitions/{montaje['comp']['id']}/enrollments")
    return [e["user_id"] for e in respuesta.json()]


class TestP1AlCerrarEsperan:
    async def test_la_pendiente_espera_y_no_se_puede_aceptar(self, client: AsyncClient):
        """
        P1. Given una pendiente y una ya rechazada / When se cierra
        Then la pendiente está ON_HOLD y aceptarla es 409 INVITATION_ON_HOLD con el texto
        aprobado; no entra; la rechazada sigue DECLINED
        """
        montaje = await _invitado_y_cerrada(client)
        suya = await _la_suya(client, montaje)
        assert suya["status"] == "ON_HOLD"

        respuesta = await client.post(
            f"/api/v1/invitations/{suya['id']}/respond", json={"action": "ACCEPT"}
        )

        assert respuesta.status_code == 409, respuesta.text
        assert respuesta.json() == {"detail": EN_ESPERA, "error_code": "INVITATION_ON_HOLD"}
        assert (await _la_suya(client, montaje))["status"] == "ON_HOLD"
        assert montaje["invitado"]["user"]["id"] not in await _inscritos(client, montaje)
        set_auth_cookies(client, montaje["ya_dijo_que_no"]["cookies"])
        suyas = (await client.get("/api/v1/invitations/me")).json()["invitations"]
        assert [i["status"] for i in suyas] == ["DECLINED"]

    async def test_el_filtro_por_estado_las_encuentra(self, client: AsyncClient):
        """P1. Given una en espera / When el invitado filtra por ON_HOLD / Then sale."""
        montaje = await _invitado_y_cerrada(client)
        set_auth_cookies(client, montaje["invitado"]["cookies"])

        respuesta = await client.get("/api/v1/invitations/me", params={"status": "ON_HOLD"})

        assert respuesta.status_code == 200, respuesta.text
        assert [i["status"] for i in respuesta.json()["invitations"]] == ["ON_HOLD"]

    async def test_rechazarla_si(self, client: AsyncClient):
        """P1. Given una en espera / When el invitado la rechaza / Then DECLINED."""
        montaje = await _invitado_y_cerrada(client)
        suya = await _la_suya(client, montaje)

        respuesta = await client.post(
            f"/api/v1/invitations/{suya['id']}/respond", json={"action": "DECLINE"}
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["status"] == "DECLINED"

    async def test_el_organizador_la_retira(self, client: AsyncClient):
        """P1. Given una en espera / When el organizador la retira / Then 204 y CANCELLED."""
        montaje = await _invitado_y_cerrada(client)
        suya = await _la_suya(client, montaje)
        set_auth_cookies(client, montaje["creador"]["cookies"])

        respuesta = await client.post(f"/api/v1/invitations/{suya['id']}/cancel")

        assert respuesta.status_code == 204, respuesta.text
        assert (await _la_suya(client, montaje))["status"] == "CANCELLED"

    async def test_cerrada_ya_no_se_invita(self, client: AsyncClient):
        """C2, como siempre: con la inscripción cerrada no se invita."""
        montaje = await _invitado_y_cerrada(client)
        otro = await create_authenticated_user(
            client, "ic_other@test.com", "P@ssw0rd123!", "Other", "Cierre"
        )
        set_auth_cookies(client, montaje["creador"]["cookies"])

        respuesta = await client.post(
            f"/api/v1/competitions/{montaje['comp']['id']}/invitations",
            json={"invitee_user_id": otro["user"]["id"]},
        )

        assert respuesta.status_code == 422, respuesta.text
        assert "plazas" in respuesta.json()["detail"]


class TestP2AlReabrirVuelven:
    async def test_vuelve_a_pendiente_avisa_y_se_acepta(self, client: AsyncClient):
        """
        P2. Given una en espera / When el organizador reabre / Then PENDING, y el
        invitado recibe «ya puedes aceptar»; al aceptarla, entra
        """
        montaje = await _invitado_y_cerrada(client)
        set_auth_cookies(client, montaje["creador"]["cookies"])
        respuesta = await client.post(
            f"/api/v1/competitions/{montaje['comp']['id']}/reopen-enrollments"
        )
        assert respuesta.status_code == 200, respuesta.text

        suya = await _la_suya(client, montaje)
        assert suya["status"] == "PENDING"
        feed = (await client.get("/api/v1/users/me/feed")).json()["events"]
        assert [e["type"] for e in feed] == ["INVITATION_ACCEPTABLE_AGAIN"]
        assert feed[0]["source_match_id"] == suya["id"]
        assert feed[0]["payload"]["competition_id"] == montaje["comp"]["id"]

        respuesta = await client.post(
            f"/api/v1/invitations/{suya['id']}/respond", json={"action": "ACCEPT"}
        )

        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["status"] == "ACCEPTED"
        assert montaje["invitado"]["user"]["id"] in await _inscritos(client, montaje)


class TestP3SinReabrirSinPlaza:
    async def test_al_empezar(self, client: AsyncClient):
        """P3. Given una en espera / When la competición empieza / Then NO_ROOM."""
        montaje = await _invitado_y_cerrada(client)
        await add_one_session(client, montaje["creador"]["cookies"], montaje["comp"])
        set_auth_cookies(client, montaje["creador"]["cookies"])
        respuesta = await client.post(f"/api/v1/competitions/{montaje['comp']['id']}/start")
        assert respuesta.status_code == 200, respuesta.text

        assert (await _la_suya(client, montaje))["status"] == "NO_ROOM"

    async def test_al_cancelarla(self, client: AsyncClient):
        """P3. Given una en espera / When se cancela la competición / Then NO_ROOM."""
        montaje = await _invitado_y_cerrada(client)
        set_auth_cookies(client, montaje["creador"]["cookies"])
        respuesta = await client.post(f"/api/v1/competitions/{montaje['comp']['id']}/cancel")
        assert respuesta.status_code == 200, respuesta.text

        assert (await _la_suya(client, montaje))["status"] == "NO_ROOM"


class TestP3CancelarAbierta:
    async def test_la_pendiente_se_queda_sin_plaza_y_se_avisa(self, client: AsyncClient):
        """P3. Given abierta con una pendiente / When se cancela / Then NO_ROOM y «no hubo plaza»."""
        creador = await create_authenticated_user(
            client, "ic_ca_org@test.com", "P@ssw0rd123!", "Org", "Cancelada"
        )
        invitado = await create_authenticated_user(
            client, "ic_ca_inv@test.com", "P@ssw0rd123!", "Invitado", "Cancelada"
        )
        comp = await create_competition(client, creador["cookies"])
        set_auth_cookies(client, creador["cookies"])
        enviada = await client.post(
            f"/api/v1/competitions/{comp['id']}/invitations",
            json={"invitee_user_id": invitado["user"]["id"]},
        )
        assert enviada.status_code == 201, enviada.text

        cancelada = await client.post(f"/api/v1/competitions/{comp['id']}/cancel")

        assert cancelada.status_code == 200, cancelada.text
        set_auth_cookies(client, invitado["cookies"])
        mias = (await client.get("/api/v1/invitations/me")).json()["invitations"]
        assert [i["status"] for i in mias] == ["NO_ROOM"]
        feed = (await client.get("/api/v1/users/me/feed")).json()["events"]
        assert [e["type"] for e in feed] == ["ENROLLMENT_NO_PLACE"]
        assert feed[0]["source_match_id"] == enviada.json()["id"]


class TestB3EquiposDeshechos:
    async def test_el_organizador_sabe_quien_entro_y_que_hay_que_rehacerlos(
        self, client: AsyncClient
    ):
        """
        B3. Given equipos formados sin partidos, reabierta, y una invitación
        When el invitado acepta
        Then el organizador ve TEAMS_UNDONE_BY_ENTRY con el jugador, y sin equipos
        """
        creador = await create_authenticated_user(
            client, "ic_b3_org@test.com", "P@ssw0rd123!", "Org", "Equipos"
        )
        jugadores = [
            await create_authenticated_user(
                client, f"ic_b3_{i}@test.com", "P@ssw0rd123!", "Jugador" + "ABC"[i], "Equipos"
            )
            for i in range(3)
        ]
        nuevo = await create_authenticated_user(
            client, "ic_b3_nuevo@test.com", "P@ssw0rd123!", "Nuevo", "Equipos"
        )
        comp = await create_competition(client, creador["cookies"])
        for jugador in jugadores:
            await inscrito_por_invitacion(client, creador["cookies"], comp["id"], jugador)
        set_auth_cookies(client, creador["cookies"])
        respuesta = await client.put(
            f"/api/v1/competitions/{comp['id']}/captains",
            json={
                "team_a_captain_id": creador["user"]["id"],
                "team_b_captain_id": jugadores[0]["user"]["id"],
            },
        )
        assert respuesta.status_code == 200, respuesta.text
        respuesta = await client.post(
            f"/api/v1/competitions/{comp['id']}/teams",
            json={"competition_id": comp["id"], "mode": "AUTOMATIC"},
        )
        assert respuesta.status_code == 201, respuesta.text
        respuesta = await client.post(f"/api/v1/competitions/{comp['id']}/reopen-enrollments")
        assert respuesta.status_code == 200, respuesta.text

        dentro = await inscrito_por_invitacion(client, creador["cookies"], comp["id"], nuevo)

        feed = (await client.get("/api/v1/users/me/feed")).json()["events"]
        [aviso] = [e for e in feed if e["type"] == "TEAMS_UNDONE_BY_ENTRY"]
        assert aviso["payload"]["competition_id"] == comp["id"]
        assert aviso["payload"]["player_id"] == nuevo["user"]["id"]
        assert aviso["source_match_id"] == dentro["enrollment_id"]
        ficha = (await client.get(f"/api/v1/competitions/{comp['id']}")).json()
        assert ficha["teams_assigned"] is False
