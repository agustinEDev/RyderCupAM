"""
Al cerrar la inscripción, las invitaciones pendientes se quedan sin plaza (#710).

Decidido el 24 sep: aceptar una invitación pendiente con la competición cerrada
metía a un jugador con el draft ya hecho (6 inscritos y 5 en equipos). Cerrar
las rechaza por falta de plazas, y cerrada ya no se invita.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


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


class TestAlCerrarLaInscripcion:
    async def test_la_pendiente_se_queda_sin_plaza_y_no_se_puede_aceptar(self, client: AsyncClient):
        montaje = await _invitado_y_cerrada(client)
        set_auth_cookies(client, montaje["invitado"]["cookies"])

        mias = (await client.get("/api/v1/invitations/me")).json()["invitations"]
        assert [i["status"] for i in mias] == ["NO_ROOM"]

        respuesta = await client.post(
            f"/api/v1/invitations/{mias[0]['id']}/respond", json={"action": "ACCEPT"}
        )
        assert respuesta.status_code == 409, respuesta.text
        # Con su codigo, para que la pantalla lo diga en su idioma (BE #385)
        assert respuesta.json()["error_code"] == "INVITATION_NO_ROOM"
        inscripciones = await client.get(
            f"/api/v1/competitions/{montaje['comp']['id']}/enrollments"
        )
        ids = [e["user_id"] for e in inscripciones.json()]
        assert montaje["invitado"]["user"]["id"] not in ids

        set_auth_cookies(client, montaje["ya_dijo_que_no"]["cookies"])
        suyas = (await client.get("/api/v1/invitations/me")).json()["invitations"]
        assert [i["status"] for i in suyas] == ["DECLINED"]

    async def test_cerrada_ya_no_se_invita(self, client: AsyncClient):
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

    async def test_reabierta_sigue_sin_plaza_y_no_dice_que_esta_cerrada(self, client: AsyncClient):
        """BE #385: reabrir no revive la invitacion, y el motivo tiene que ser
        cierto tambien entonces. Decia «la inscripción está cerrada» con la
        competicion ACTIVE otra vez."""
        montaje = await _invitado_y_cerrada(client)
        set_auth_cookies(client, montaje["creador"]["cookies"])
        respuesta = await client.post(
            f"/api/v1/competitions/{montaje['comp']['id']}/reopen-enrollments"
        )
        assert respuesta.status_code == 200, respuesta.text

        set_auth_cookies(client, montaje["invitado"]["cookies"])
        suya = (await client.get("/api/v1/invitations/me")).json()["invitations"][0]
        respuesta = await client.post(
            f"/api/v1/invitations/{suya['id']}/respond", json={"action": "ACCEPT"}
        )

        assert respuesta.status_code == 409, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["error_code"] == "INVITATION_NO_ROOM"
        assert "cerrada" not in cuerpo["detail"]
