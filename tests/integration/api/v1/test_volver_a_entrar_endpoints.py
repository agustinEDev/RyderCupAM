"""
Volver a entrar con una inscripción vieja, contra Postgres (release social 2, 27 oct 2026).

La restricción única (competición, usuario) no mira el estado: el arreglo
reutiliza la fila cerrada, y aquí se ve que la base de datos lo acepta.
"""

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient

from src.shared.domain.services.instante_utc import ahora_utc_sin_zona
from tests.conftest import (
    create_authenticated_user,
    create_competition,
    inscrito_por_invitacion,
    set_auth_cookies,
    solicitud_pendiente,
)

pytestmark = pytest.mark.asyncio


async def _jugador(client: AsyncClient) -> dict:
    nombre = uuid.uuid4().hex[:6]
    return await create_authenticated_user(
        client, f"vae_{nombre}@test.com", "P@ssw0rd123!", "Vuelve", "Entrar"
    )


async def _publica(client: AsyncClient, creador: dict) -> dict:
    start = ahora_utc_sin_zona().date() + timedelta(days=30)
    return await create_competition(
        client,
        creador["cookies"],
        {
            "name": f"Vuelve {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 10,
            "team_assignment": "MANUAL",
            "visibility": "PUBLIC",
        },
    )


async def _pide(client: AsyncClient, jugador: dict, comp: dict):
    set_auth_cookies(client, jugador["cookies"])
    return await client.post(f"/api/v1/competitions/{comp['id']}/enrollments", json={})


async def test_rechazada_vuelve_a_pedir_y_luego_acepta_una_invitacion(client: AsyncClient):
    creador, jugador = await _jugador(client), await _jugador(client)
    comp = await _publica(client, creador)
    # Una solicitud de antes de la inscripción directa (28 oct 2026), rechazada
    set_auth_cookies(client, jugador["cookies"])
    pedida = await solicitud_pendiente(client, comp["id"])
    set_auth_cookies(client, creador["cookies"])
    assert (await client.post(f"/api/v1/enrollments/{pedida['id']}/reject")).status_code == 200

    # V2: vuelve a apuntarse, con la misma fila, y ya entra
    otra = await _pide(client, jugador, comp)
    assert otra.status_code == 201, otra.text
    assert otra.json()["id"] == pedida["id"]
    assert otra.json()["status"] == "APPROVED"

    # El organizador le quita, y le invita: V1, entra
    set_auth_cookies(client, creador["cookies"])
    assert (await client.post(f"/api/v1/enrollments/{otra.json()['id']}/remove")).status_code == 200
    invitacion = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": jugador["user"]["id"]},
    )
    assert invitacion.status_code == 201, invitacion.text
    set_auth_cookies(client, jugador["cookies"])
    aceptada = await client.post(
        f"/api/v1/invitations/{invitacion.json()['id']}/respond", json={"action": "ACCEPT"}
    )

    assert aceptada.status_code == 200, aceptada.text
    assert aceptada.json()["enrollment_id"] == pedida["id"]


async def _estado_de(client: AsyncClient, creador: dict, comp: dict, jugador: dict) -> str:
    set_auth_cookies(client, creador["cookies"])
    todas = (await client.get(f"/api/v1/competitions/{comp['id']}/enrollments")).json()
    return next(e["status"] for e in todas if e["user_id"] == jugador["user"]["id"])


async def test_o6_el_retirado_solo_vuelve_si_acepta(client: AsyncClient):
    """
    B-02 (15 nov 2026), O6: nadie vuelve sin su consentimiento.

    Given un jugador que entró por invitación y se retiró / When el organizador
    intenta la vieja inscripción directa / Then no existe y sigue WITHDRAWN.
    When le invita / Then sigue WITHDRAWN hasta que él acepta, y entonces vuelve
    con la misma fila.
    """
    creador, jugador = await _jugador(client), await _jugador(client)
    comp = await _publica(client, creador)
    dentro = await inscrito_por_invitacion(client, creador["cookies"], comp["id"], jugador)
    set_auth_cookies(client, jugador["cookies"])
    retirada = await client.post(f"/api/v1/enrollments/{dentro['enrollment_id']}/withdraw", json={})
    assert retirada.status_code == 200, retirada.text

    set_auth_cookies(client, creador["cookies"])
    directa = await client.post(
        f"/api/v1/competitions/{comp['id']}/enrollments/direct",
        json={"competition_id": comp["id"], "user_id": jugador["user"]["id"]},
    )
    assert directa.status_code in (404, 405), directa.text
    assert await _estado_de(client, creador, comp, jugador) == "WITHDRAWN"

    set_auth_cookies(client, creador["cookies"])
    enviada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": jugador["user"]["id"]},
    )
    assert enviada.status_code == 201, enviada.text
    assert await _estado_de(client, creador, comp, jugador) == "WITHDRAWN"

    set_auth_cookies(client, jugador["cookies"])
    aceptada = await client.post(
        f"/api/v1/invitations/{enviada.json()['id']}/respond", json={"action": "ACCEPT"}
    )

    assert aceptada.status_code == 200, aceptada.text
    assert aceptada.json()["enrollment_id"] == dentro["enrollment_id"]
    assert await _estado_de(client, creador, comp, jugador) == "APPROVED"


async def test_r4_tras_una_pendiente_ya_caducada_sale_otra(client: AsyncClient):
    """Con el índice único de pendientes: la vieja pasa a EXPIRED antes de la nueva."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.conftest import _URL_DE_LA_BD_DE_TEST

    creador, jugador = await _jugador(client), await _jugador(client)
    comp = await _publica(client, creador)
    set_auth_cookies(client, creador["cookies"])
    url = f"/api/v1/competitions/{comp['id']}/invitations"
    primera = await client.post(url, json={"invitee_user_id": jugador["user"]["id"]})
    assert primera.status_code == 201, primera.text
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE invitations SET expires_at = now() - interval '1 hour', "
                    "created_at = now() - interval '8 days' WHERE id = :id"
                ),
                {"id": primera.json()["id"]},
            )
    finally:
        await engine.dispose()

    segunda = await client.post(url, json={"invitee_user_id": jugador["user"]["id"]})

    assert segunda.status_code == 201, segunda.text
    assert segunda.json()["id"] != primera.json()["id"]
