"""
Invitar solo con plazas, retirar una invitación y llenarse (BE #359).

- Retirar: `POST /invitations/{id}/cancel` → 204; la invitación queda CANCELLED.
- Sin plazas no se invita: 409 con `error_code` COMPETITION_FULL, para que la
  pantalla lo diga en su idioma.
- La aceptación que llena la última plaza deja sin plaza (NO_ROOM) a las demás.
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, create_competition, set_auth_cookies

pytestmark = pytest.mark.asyncio


async def _jugador(client: AsyncClient, nombre: str) -> dict:
    return await create_authenticated_user(
        client, f"ipr_{nombre.lower()}@test.com", "P@ssw0rd123!", nombre, "Plazas"
    )


async def _competicion(client: AsyncClient, creador: dict, plazas: int) -> dict:
    start = date.today() + timedelta(days=30)
    return await create_competition(
        client,
        creador["cookies"],
        {
            "name": f"Plazas {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            # El organizador ya ocupa una al crearla
            "max_players": plazas,
            "team_assignment": "MANUAL",
            "visibility": "PUBLIC",
        },
    )


async def _invita(client: AsyncClient, creador: dict, comp: dict, jugador: dict):
    set_auth_cookies(client, creador["cookies"])
    return await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": jugador["user"]["id"]},
    )


async def _la_suya(client: AsyncClient, jugador: dict) -> dict:
    set_auth_cookies(client, jugador["cookies"])
    return (await client.get("/api/v1/invitations/me")).json()["invitations"][0]


class TestRetirar:
    async def test_el_organizador_la_retira_y_ya_no_se_puede_aceptar(self, client: AsyncClient):
        creador = await _jugador(client, "Creador")
        invitado = await _jugador(client, "Invitado")
        comp = await _competicion(client, creador, plazas=6)
        assert (await _invita(client, creador, comp, invitado)).status_code == 201
        suya = await _la_suya(client, invitado)

        set_auth_cookies(client, creador["cookies"])
        respuesta = await client.post(f"/api/v1/invitations/{suya['id']}/cancel")
        assert respuesta.status_code == 204, respuesta.text

        assert (await _la_suya(client, invitado))["status"] == "CANCELLED"
        respuesta = await client.post(
            f"/api/v1/invitations/{suya['id']}/respond", json={"action": "ACCEPT"}
        )
        assert respuesta.status_code == 409, respuesta.text

    async def test_otro_usuario_no_puede(self, client: AsyncClient):
        creador = await _jugador(client, "Creador")
        invitado = await _jugador(client, "Invitado")
        comp = await _competicion(client, creador, plazas=6)
        await _invita(client, creador, comp, invitado)
        suya = await _la_suya(client, invitado)

        # Ni el propio invitado: para decir que no, está «rechazar»
        respuesta = await client.post(f"/api/v1/invitations/{suya['id']}/cancel")

        assert respuesta.status_code == 403, respuesta.text
        assert (await _la_suya(client, invitado))["status"] == "PENDING"

    async def test_una_ya_respondida_da_409(self, client: AsyncClient):
        creador = await _jugador(client, "Creador")
        invitado = await _jugador(client, "Invitado")
        comp = await _competicion(client, creador, plazas=6)
        await _invita(client, creador, comp, invitado)
        suya = await _la_suya(client, invitado)
        await client.post(f"/api/v1/invitations/{suya['id']}/respond", json={"action": "DECLINE"})

        set_auth_cookies(client, creador["cookies"])
        respuesta = await client.post(f"/api/v1/invitations/{suya['id']}/cancel")

        assert respuesta.status_code == 409, respuesta.text

    async def test_una_que_no_existe_da_404(self, client: AsyncClient):
        creador = await _jugador(client, "Creador")
        set_auth_cookies(client, creador["cookies"])

        respuesta = await client.post(f"/api/v1/invitations/{uuid.uuid4()}/cancel")

        assert respuesta.status_code == 404, respuesta.text


class TestPlazas:
    async def test_sin_plazas_no_se_invita_y_lo_dice_con_su_codigo(self, client: AsyncClient):
        creador = await _jugador(client, "Creador")
        dentro = await _jugador(client, "Dentro")
        fuera = await _jugador(client, "Fuera")
        comp = await _competicion(client, creador, plazas=2)
        await _invita(client, creador, comp, dentro)
        suya = await _la_suya(client, dentro)
        respuesta = await client.post(
            f"/api/v1/invitations/{suya['id']}/respond", json={"action": "ACCEPT"}
        )
        assert respuesta.status_code == 200, respuesta.text

        respuesta = await _invita(client, creador, comp, fuera)

        assert respuesta.status_code == 409, respuesta.text
        assert respuesta.json()["error_code"] == "COMPETITION_FULL"
        # Con un texto fijo, sin datos internos: el de la excepción llevaba el id
        # de la competición y los recuentos (CodeQL en la #488)
        assert comp["id"] not in respuesta.json()["detail"]

    async def test_la_que_llena_la_ultima_plaza_deja_sin_plaza_a_las_demas(
        self, client: AsyncClient
    ):
        creador = await _jugador(client, "Creador")
        primero = await _jugador(client, "Primero")
        tarde = await _jugador(client, "Tarde")
        comp = await _competicion(client, creador, plazas=2)
        await _invita(client, creador, comp, primero)
        await _invita(client, creador, comp, tarde)

        suya = await _la_suya(client, primero)
        respuesta = await client.post(
            f"/api/v1/invitations/{suya['id']}/respond", json={"action": "ACCEPT"}
        )
        assert respuesta.status_code == 200, respuesta.text

        assert (await _la_suya(client, tarde))["status"] == "NO_ROOM"


class TestLoQueSeDice:
    """Probado en bloque en el Kind antes de la 2.26.0 (5 oct)."""

    async def test_llena_con_el_freno_agotado_dice_que_esta_llena(self, client: AsyncClient):
        creador = await _jugador(client, "Creador")
        primero = await _jugador(client, "Primero")
        segundo = await _jugador(client, "Segundo")
        fuera = await _jugador(client, "Fuera")
        # Cupo 2: el freno por hora es 2 y las dos invitaciones lo agotan
        comp = await _competicion(client, creador, plazas=2)
        await _invita(client, creador, comp, primero)
        await _invita(client, creador, comp, segundo)
        suya = await _la_suya(client, primero)
        await client.post(f"/api/v1/invitations/{suya['id']}/respond", json={"action": "ACCEPT"})

        respuesta = await _invita(client, creador, comp, fuera)

        assert respuesta.status_code == 409, respuesta.text
        assert respuesta.json()["error_code"] == "COMPETITION_FULL"

    async def test_el_freno_lleva_codigo_y_limite_sin_datos_internos(self, client: AsyncClient):
        creador = await _jugador(client, "Creador")
        uno = await _jugador(client, "Uno")
        dos = await _jugador(client, "Dos")
        tres = await _jugador(client, "Tres")
        comp = await _competicion(client, creador, plazas=3)
        await _invita(client, creador, comp, uno)
        await _invita(client, creador, comp, dos)

        respuesta = await _invita(client, creador, comp, tres)
        assert respuesta.status_code == 201, respuesta.text
        cuarto = await _jugador(client, "Cuarto")
        respuesta = await _invita(client, creador, comp, cuarto)

        assert respuesta.status_code == 429, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo["error_code"] == "INVITATION_RATE_LIMIT"
        assert cuerpo["limit"] == 3
        assert comp["id"] not in cuerpo["detail"]

    async def test_el_freno_por_correo_tambien(self, client: AsyncClient):
        creador = await _jugador(client, "Creador")
        comp = await _competicion(client, creador, plazas=2)
        set_auth_cookies(client, creador["cookies"])
        for correo in ("a@test.com", "b@test.com"):
            await client.post(
                f"/api/v1/competitions/{comp['id']}/invitations/by-email",
                json={"invitee_email": correo},
            )

        respuesta = await client.post(
            f"/api/v1/competitions/{comp['id']}/invitations/by-email",
            json={"invitee_email": "c@test.com"},
        )

        assert respuesta.status_code == 429, respuesta.text
        assert respuesta.json()["error_code"] == "INVITATION_RATE_LIMIT"
        assert respuesta.json()["limit"] == 2

    async def test_sin_plaza_por_llenarse_no_habla_de_cierre(self, client: AsyncClient):
        creador = await _jugador(client, "Creador")
        primero = await _jugador(client, "Primero")
        tarde = await _jugador(client, "Tarde")
        comp = await _competicion(client, creador, plazas=2)
        await _invita(client, creador, comp, primero)
        await _invita(client, creador, comp, tarde)
        suya = await _la_suya(client, primero)
        await client.post(f"/api/v1/invitations/{suya['id']}/respond", json={"action": "ACCEPT"})

        la_de_tarde = await _la_suya(client, tarde)
        respuesta = await client.post(
            f"/api/v1/invitations/{la_de_tarde['id']}/respond", json={"action": "ACCEPT"}
        )

        assert respuesta.status_code == 409, respuesta.text
        assert respuesta.json() == {
            "detail": "Esta invitación se quedó sin plaza",
            "error_code": "INVITATION_NO_ROOM",
        }
