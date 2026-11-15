"""
Correo verificado para lo que llega a otras personas (B-17 de la auditoría de la fase 6),
por la API real.

    caso                                              | sin verificar     | verificado
    --------------------------------------------------|-------------------|-----------
    V1 crear una competición                          | 403 EMAIL_NOT_... | 201
    V2 pedir amistad                                  | 403 EMAIL_NOT_... | 201
    V3 invitar por usuario y por correo               | 403 EMAIL_NOT_... | 201
    V4 aceptar una solicitud de amistad               | 200               | 200
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies, sql_en_la_bd_de_test

pytestmark = pytest.mark.asyncio

CLAVE = "P@ssw0rd123!"


def _correo(nombre: str) -> str:
    return f"{nombre}.{uuid.uuid4().hex[:8]}@example.com"


def _csrf(client: AsyncClient) -> dict:
    return {"X-CSRF-Token": client.cookies.get("csrf_token") or ""}


async def _usuario(client: AsyncClient, nombre: str, verificado: bool) -> dict:
    return await create_authenticated_user(
        client, _correo(nombre), CLAVE, nombre.capitalize(), "Prueba", verificar=verificado
    )


async def _crea_competicion(client: AsyncClient, quien: dict):
    set_auth_cookies(client, quien["cookies"])
    return await client.post(
        "/api/v1/competitions",
        headers=_csrf(client),
        json={
            "name": f"B17 {uuid.uuid4().hex[:6]}",
            "start_date": "2027-06-01",
            "end_date": "2027-06-02",
            "main_country": "ES",
            "play_mode": "SCRATCH",
        },
    )


async def test_v1_creating_a_competition(client: AsyncClient):
    sin = await _usuario(client, "sinuno", False)
    con = await _usuario(client, "conuno", True)

    rechazo = await _crea_competicion(client, sin)
    creada = await _crea_competicion(client, con)

    assert rechazo.status_code == 403
    assert rechazo.json()["error_code"] == "EMAIL_NOT_VERIFIED"
    assert creada.status_code == 201, creada.text


async def test_v2_v4_friend_requests(client: AsyncClient):
    sin = await _usuario(client, "sindos", False)
    con = await _usuario(client, "condos", True)

    set_auth_cookies(client, sin["cookies"])
    rechazo = await client.post(
        "/api/v1/friends/requests", headers=_csrf(client), json={"addressee_id": con["user"]["id"]}
    )
    set_auth_cookies(client, con["cookies"])
    enviada = await client.post(
        "/api/v1/friends/requests", headers=_csrf(client), json={"addressee_id": sin["user"]["id"]}
    )
    set_auth_cookies(client, sin["cookies"])
    aceptada = await client.post(
        f"/api/v1/friends/requests/{enviada.json()['id']}/respond",
        headers=_csrf(client),
        json={"action": "ACCEPT"},
    )

    assert rechazo.status_code == 403
    assert rechazo.json()["error_code"] == "EMAIL_NOT_VERIFIED"
    assert enviada.status_code == 201, enviada.text
    assert aceptada.status_code == 200, aceptada.text


async def test_v3_inviting(client: AsyncClient):
    organizador = await _usuario(client, "organizador", True)
    creada = await _crea_competicion(client, organizador)
    competicion = creada.json()["id"]
    invitado = await _usuario(client, "invitado", True)
    # El mismo organizador, ahora sin verificar (como si hubiera cambiado su correo)
    await sql_en_la_bd_de_test(
        "update users set email_verified = false where id = :i", i=organizador["user"]["id"]
    )
    set_auth_cookies(client, organizador["cookies"])
    por_usuario = await client.post(
        f"/api/v1/competitions/{competicion}/invitations",
        headers=_csrf(client),
        json={"invitee_user_id": invitado["user"]["id"]},
    )
    por_correo = await client.post(
        f"/api/v1/competitions/{competicion}/invitations/by-email",
        headers=_csrf(client),
        json={"invitee_email": _correo("alguien")},
    )
    await sql_en_la_bd_de_test(
        "update users set email_verified = true where id = :i", i=organizador["user"]["id"]
    )
    verificado = await client.post(
        f"/api/v1/competitions/{competicion}/invitations",
        headers=_csrf(client),
        json={"invitee_user_id": invitado["user"]["id"]},
    )

    for rechazo in (por_usuario, por_correo):
        assert rechazo.status_code == 403, rechazo.text
        assert rechazo.json()["error_code"] == "EMAIL_NOT_VERIFIED"
    assert verificado.status_code == 201, verificado.text
