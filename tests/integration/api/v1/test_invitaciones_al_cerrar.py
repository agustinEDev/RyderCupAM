"""
El organizador solo invita, también con la inscripción cerrada (B-02, 15 nov 2026).

Del 24 sep (#710) al 15 nov cerrar la inscripción rechazaba las invitaciones
pendientes «sin plaza» y cerrada ya no se invitaba. Desde B-02, por la API:

| #  | Caso                                                | Debe                                   |
|----|-----------------------------------------------------|----------------------------------------|
| O4 | Cerrar la inscripción con una pendiente             | Sigue PENDING                          |
| O3 | Aceptarla con la inscripción cerrada                | 200: entra, y la competición sigue cerrada |
| O3 | Aceptar cerrada cuando otra llenó la última plaza   | 409 INVITATION_NO_ROOM, como hoy       |
| O2 | Invitar con la inscripción cerrada (Ryder)          | 201, PENDING                           |
| O4 | Cerrar y reabrir                                    | Sigue PENDING y se acepta              |
| O5 | Empezar la competición                              | La pendiente, NO_ROOM; aceptar es 409  |
| O5 | Invitar ya empezada                                 | 422                                    |
| P1 | Stableford cerrado: invitar                         | 422 («plazas»)                         |
| P1 | Stableford cerrado: aceptar una pendiente           | 422 («reabrir»); sigue PENDING         |
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    add_one_session,
    create_authenticated_user,
    create_competition,
    plaza_para_todos,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio

PASSWORD = "P@ssw0rd123!"


async def _usuario(client: AsyncClient, prefijo: str, handicap: float | None = None) -> dict:
    usuario = await create_authenticated_user(
        client, f"{prefijo}-{uuid.uuid4().hex[:8]}@test.com", PASSWORD, "Ana", "Cierre"
    )
    if handicap is not None:
        set_auth_cookies(client, usuario["cookies"])
        respuesta = await client.post(
            "/api/v1/handicaps/update",
            json={"user_id": usuario["user"]["id"], "manual_handicap": handicap},
        )
        assert respuesta.status_code == 200, respuesta.text
    return usuario


async def _invita(client: AsyncClient, creador: dict, comp: dict, invitado: dict):
    set_auth_cookies(client, creador["cookies"])
    return await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": invitado["user"]["id"]},
    )


async def _acepta(client: AsyncClient, invitado: dict, invitacion_id: str):
    set_auth_cookies(client, invitado["cookies"])
    return await client.post(
        f"/api/v1/invitations/{invitacion_id}/respond", json={"action": "ACCEPT"}
    )


async def _mias(client: AsyncClient, invitado: dict) -> list[str]:
    set_auth_cookies(client, invitado["cookies"])
    respuesta = await client.get("/api/v1/invitations/me")
    return [i["status"] for i in respuesta.json()["invitations"]]


async def _cierra(client: AsyncClient, creador: dict, comp: dict) -> None:
    set_auth_cookies(client, creador["cookies"])
    respuesta = await client.post(f"/api/v1/competitions/{comp['id']}/close-enrollments")
    assert respuesta.status_code == 200, respuesta.text


async def _estado(client: AsyncClient, creador: dict, comp: dict) -> str:
    set_auth_cookies(client, creador["cookies"])
    return (await client.get(f"/api/v1/competitions/{comp['id']}")).json()["status"]


async def _pendiente_y_cerrada(client: AsyncClient, max_players: int | None = None) -> dict:
    """Una Ryder con una invitación enviada abierta, y la inscripción cerrada después."""
    creador = await _usuario(client, "ic-org")
    invitado = await _usuario(client, "ic-inv")
    datos = None
    if max_players is not None:
        start = date.today() + timedelta(days=30)
        datos = {
            "name": f"Cierre {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": max_players,
            "team_assignment": "MANUAL",
        }
    comp = await create_competition(client, creador["cookies"], datos)
    enviada = await _invita(client, creador, comp, invitado)
    assert enviada.status_code == 201, enviada.text
    await _cierra(client, creador, comp)
    return {"creador": creador, "invitado": invitado, "comp": comp, "id": enviada.json()["id"]}


class TestO3O4CerrarYAceptar:
    async def test_cerrar_deja_la_pendiente_y_aceptarla_entra(self, client: AsyncClient):
        """
        Given una invitación pendiente / When se cierra la inscripción / Then sigue
        PENDING. When la acepta / Then 200, entra, y la competición sigue cerrada.
        """
        m = await _pendiente_y_cerrada(client)
        assert await _mias(client, m["invitado"]) == ["PENDING"]

        aceptada = await _acepta(client, m["invitado"], m["id"])

        assert aceptada.status_code == 200, aceptada.text
        assert aceptada.json()["status"] == "ACCEPTED"
        assert aceptada.json()["enrollment_id"] is not None
        set_auth_cookies(client, m["creador"]["cookies"])
        inscritos = await client.get(
            f"/api/v1/competitions/{m['comp']['id']}/enrollments?status=APPROVED"
        )
        assert m["invitado"]["user"]["id"] in [e["user_id"] for e in inscritos.json()]
        assert await _estado(client, m["creador"], m["comp"]) == "CLOSED"

    async def test_sin_sitio_sin_plaza_como_hoy(self, client: AsyncClient):
        """
        Given una cerrada de 2 plazas (el organizador ocupa una) y dos pendientes /
        When la primera la llena / Then la segunda es 409 INVITATION_NO_ROOM.
        """
        m = await _pendiente_y_cerrada(client, max_players=2)
        tarde = await _usuario(client, "ic-tarde")
        # Enviada ya cerrada (O2): cabe mientras no se llene
        enviada = await _invita(client, m["creador"], m["comp"], tarde)
        assert enviada.status_code == 201, enviada.text
        assert (await _acepta(client, m["invitado"], m["id"])).status_code == 200

        respuesta = await _acepta(client, tarde, enviada.json()["id"])

        assert respuesta.status_code == 409, respuesta.text
        assert respuesta.json()["error_code"] == "INVITATION_NO_ROOM"

    async def test_reabierta_sigue_pendiente_y_se_acepta(self, client: AsyncClient):
        m = await _pendiente_y_cerrada(client)
        set_auth_cookies(client, m["creador"]["cookies"])
        reabierta = await client.post(f"/api/v1/competitions/{m['comp']['id']}/reopen-enrollments")
        assert reabierta.status_code == 200, reabierta.text

        aceptada = await _acepta(client, m["invitado"], m["id"])

        assert aceptada.status_code == 200, aceptada.text


class TestO2InvitarCerrada:
    async def test_cerrada_se_invita(self, client: AsyncClient):
        """Given una Ryder cerrada / When el organizador invita / Then 201 PENDING, y
        sigue cerrada."""
        m = await _pendiente_y_cerrada(client)
        otro = await _usuario(client, "ic-otro")

        respuesta = await _invita(client, m["creador"], m["comp"], otro)

        assert respuesta.status_code == 201, respuesta.text
        assert respuesta.json()["status"] == "PENDING"
        assert await _estado(client, m["creador"], m["comp"]) == "CLOSED"


class TestO5Empezar:
    async def _empezada(self, client: AsyncClient) -> dict:
        m = await _pendiente_y_cerrada(client)
        await add_one_session(client, m["creador"]["cookies"], m["comp"])
        set_auth_cookies(client, m["creador"]["cookies"])
        empezada = await client.post(f"/api/v1/competitions/{m['comp']['id']}/start")
        assert empezada.status_code == 200, empezada.text
        return m

    async def test_empezar_la_deja_sin_plaza_y_no_se_acepta(self, client: AsyncClient):
        m = await self._empezada(client)

        assert await _mias(client, m["invitado"]) == ["NO_ROOM"]
        respuesta = await _acepta(client, m["invitado"], m["id"])

        assert respuesta.status_code == 409, respuesta.text
        assert respuesta.json()["error_code"] == "INVITATION_NO_ROOM"

    async def test_empezada_no_se_invita(self, client: AsyncClient):
        m = await self._empezada(client)
        otro = await _usuario(client, "ic-otro")

        respuesta = await _invita(client, m["creador"], m["comp"], otro)

        assert respuesta.status_code == 422, respuesta.text
        assert "plazas" in respuesta.json()["detail"]


class TestP1StrokePlayCerrado:
    async def _cerrado(self, client: AsyncClient) -> dict:
        """Un Stableford con una invitación pendiente, y la inscripción cerrada."""
        creador = await _usuario(client, "ic-sp-org", handicap=14.2)
        invitado = await _usuario(client, "ic-sp-inv", handicap=20.0)
        start = date.today() + timedelta(days=30)
        comp = await create_competition(
            client,
            creador["cookies"],
            {
                "name": f"Medal {uuid.uuid4().hex[:8]}",
                "start_date": start.isoformat(),
                "end_date": start.isoformat(),
                "main_country": "ES",
                "play_mode": "HANDICAP",
                "tournament_type": "STABLEFORD",
                "stroke_play": {"category_limits": [12.0]},
            },
        )
        enviada = await _invita(client, creador, comp, invitado)
        assert enviada.status_code == 201, enviada.text
        await plaza_para_todos(client, creador["cookies"], comp)
        await _cierra(client, creador, comp)
        return {"creador": creador, "invitado": invitado, "comp": comp, "id": enviada.json()["id"]}

    async def test_no_se_invita(self, client: AsyncClient):
        m = await self._cerrado(client)
        otro = await _usuario(client, "ic-sp-otro", handicap=10.0)

        respuesta = await _invita(client, m["creador"], m["comp"], otro)

        assert respuesta.status_code == 422, respuesta.text
        assert "plazas" in respuesta.json()["detail"]

    async def test_aceptar_no_entra_y_sigue_pendiente(self, client: AsyncClient):
        m = await self._cerrado(client)

        respuesta = await _acepta(client, m["invitado"], m["id"])

        assert respuesta.status_code == 422, respuesta.text
        assert "reabrir" in respuesta.json()["detail"]
        assert await _mias(client, m["invitado"]) == ["PENDING"]
