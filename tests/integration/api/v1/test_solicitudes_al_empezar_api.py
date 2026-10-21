"""
Al empezar la competición, las solicitudes pendientes se rechazan (decidido el
21 oct). Cerrar la inscripción no las toca: en una Ryder el organizador aún puede
aprobarlas.

El probador vio una solicitud REQUESTED con la competición ya empezada, y al
organizador todavía le salían «Aprobar» y «Rechazar».
"""

import pytest
from httpx import AsyncClient

from tests.conftest import (
    add_one_session,
    create_authenticated_user,
    create_competition,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio


async def _con_una_solicitud(client: AsyncClient, prefijo: str) -> tuple[dict, dict, dict, str]:
    """Una Ryder abierta y un jugador que ha pedido plaza."""
    creador = await create_authenticated_user(
        client, f"{prefijo}_creator@test.com", "P@ssw0rd123!", "Creator", "Solicitud"
    )
    jugador = await create_authenticated_user(
        client, f"{prefijo}_player@test.com", "P@ssw0rd123!", "Player", "Solicitud"
    )
    comp = await create_competition(client, creador["cookies"])
    set_auth_cookies(client, jugador["cookies"])
    pedida = await client.post(f"/api/v1/competitions/{comp['id']}/enrollments")
    assert pedida.status_code == 201, pedida.text
    assert pedida.json()["status"] == "REQUESTED"
    return creador, jugador, comp, pedida.json()["id"]


async def _estado_de_su_inscripcion(client: AsyncClient, creador, jugador, comp) -> str:
    set_auth_cookies(client, creador["cookies"])
    lista = await client.get(f"/api/v1/competitions/{comp['id']}/enrollments")
    assert lista.status_code == 200, lista.text
    return next(e["status"] for e in lista.json() if e["user_id"] == jugador["user"]["id"])


async def _pendientes(client: AsyncClient, creador, comp) -> int:
    set_auth_cookies(client, creador["cookies"])
    respuesta = await client.get(f"/api/v1/competitions/{comp['id']}")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["pending_enrollments_count"]


async def _cerrar(client: AsyncClient, creador, comp) -> None:
    set_auth_cookies(client, creador["cookies"])
    cerrada = await client.post(f"/api/v1/competitions/{comp['id']}/close-enrollments")
    assert cerrada.status_code == 200, cerrada.text


async def test_cerrar_no_la_rechaza_y_en_una_ryder_aun_se_aprueba(client: AsyncClient):
    creador, jugador, comp, solicitud_id = await _con_una_solicitud(client, "sa_cerrar")

    await _cerrar(client, creador, comp)

    assert await _estado_de_su_inscripcion(client, creador, jugador, comp) == "REQUESTED"
    assert await _pendientes(client, creador, comp) == 1

    set_auth_cookies(client, creador["cookies"])
    aprobada = await client.post(f"/api/v1/enrollments/{solicitud_id}/approve")
    assert aprobada.status_code == 200, aprobada.text
    assert await _estado_de_su_inscripcion(client, creador, jugador, comp) == "APPROVED"


async def test_iniciar_la_rechaza_y_ya_no_se_puede_aprobar(client: AsyncClient):
    creador, jugador, comp, solicitud_id = await _con_una_solicitud(client, "sa_iniciar")
    await _cerrar(client, creador, comp)
    await add_one_session(client, creador["cookies"], comp)

    set_auth_cookies(client, creador["cookies"])
    iniciada = await client.post(f"/api/v1/competitions/{comp['id']}/start")
    assert iniciada.status_code == 200, iniciada.text

    assert await _estado_de_su_inscripcion(client, creador, jugador, comp) == "REJECTED"
    assert await _pendientes(client, creador, comp) == 0

    set_auth_cookies(client, creador["cookies"])
    aprobada = await client.post(f"/api/v1/enrollments/{solicitud_id}/approve")
    assert aprobada.status_code == 400, aprobada.text
    assert await _estado_de_su_inscripcion(client, creador, jugador, comp) == "REJECTED"
