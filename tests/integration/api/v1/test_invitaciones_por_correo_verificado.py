"""
Invitaciones por correo solo con el correo verificado, por la API (F-07, fase 3).

  D2 por correo y cuenta verificada: la ve, la acepta, ve la privada y la ficha la ofrece
  D3 sin verificar: ni en /invitations/me, ni la privada en el listado, ni en la
     ficha; responderla da el mismo 404 que una inexistente
  D4 al verificar, aparece
  D1 dirigida a la cuenta: sin cambios aunque no esté verificada
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import (
    create_authenticated_user,
    create_competition,
    set_auth_cookies,
    sql_en_la_bd_de_test,
)

pytestmark = pytest.mark.asyncio

CLAVE = "P@ssw0rd123!"


async def _jugador(client: AsyncClient, email: str) -> dict:
    return await create_authenticated_user(client, email, CLAVE, "Ana", "Correo")


async def _verifica(email: str) -> None:
    await sql_en_la_bd_de_test("update users set email_verified = true where email = :e", e=email)


async def _privada(client: AsyncClient, creador: dict) -> dict:
    start = date.today() + timedelta(days=30)
    return await create_competition(
        client,
        creador["cookies"],
        {
            "name": f"Privada {uuid.uuid4().hex[:8]}",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=1)).isoformat(),
            "main_country": "ES",
            "play_mode": "HANDICAP",
            "max_players": 12,
            "team_assignment": "MANUAL",
            "visibility": "PRIVATE",
        },
    )


async def _invitada_por_correo(client: AsyncClient) -> tuple[dict, dict, dict, str]:
    """La invitación sale a un correo sin cuenta; luego esa dirección se da de alta."""
    sufijo = uuid.uuid4().hex[:8]
    creador = await _jugador(client, f"org-{sufijo}@test.com")
    comp = await _privada(client, creador)
    correo = f"invitada-{sufijo}@test.com"
    set_auth_cookies(client, creador["cookies"])
    r = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations/by-email",
        json={"invitee_email": correo},
    )
    assert r.status_code == 201, r.text
    client.cookies.clear()
    invitada = await _jugador(client, correo)
    return invitada, comp, r.json(), correo


async def _mis_invitaciones(client: AsyncClient, jugador: dict) -> dict:
    set_auth_cookies(client, jugador["cookies"])
    r = await client.get("/api/v1/invitations/me")
    assert r.status_code == 200, r.text
    return r.json()


async def _listado(client: AsyncClient, jugador: dict) -> set[str]:
    set_auth_cookies(client, jugador["cookies"])
    r = await client.get("/api/v1/competitions")
    assert r.status_code == 200, r.text
    return {c["id"] for c in r.json()}


async def _ficha(client: AsyncClient, jugador: dict, comp: dict) -> dict:
    set_auth_cookies(client, jugador["cookies"])
    r = await client.get(f"/api/v1/competitions/{comp['id']}")
    assert r.status_code == 200, r.text
    return r.json()


async def _responde(client: AsyncClient, jugador: dict, invitation_id: str, action: str):
    set_auth_cookies(client, jugador["cookies"])
    return await client.post(
        f"/api/v1/invitations/{invitation_id}/respond",
        json={"action": action},
        headers={"X-CSRF-Token": jugador["cookies"].get("csrf_token", "")},
    )


async def test_d3_sin_verificar_no_la_ve_en_ningun_sitio(client: AsyncClient):
    """
    Given: Una invitación a un correo, y la cuenta de ese correo sin verificar
    When: Mira sus invitaciones, el listado de competiciones y la ficha
    Then: No está en ninguno: ni la invitación, ni la privada, ni la ficha la ofrece
    """
    invitada, comp, _, _ = await _invitada_por_correo(client)

    mias = await _mis_invitaciones(client, invitada)
    assert mias["invitations"] == []
    assert mias["total_count"] == 0
    assert comp["id"] not in await _listado(client, invitada)
    assert (await _ficha(client, invitada, comp))["my_pending_invitation"] is None


@pytest.mark.parametrize("action", ["ACCEPT", "DECLINE"])
async def test_d3_sin_verificar_responderla_da_el_404_de_una_inexistente(
    client: AsyncClient, action: str
):
    """
    Given: Una invitación a un correo, y la cuenta de ese correo sin verificar
    When: La acepta o la rechaza
    Then: El mismo 404 que una invitación que no existe
    """
    invitada, _, invitacion, _ = await _invitada_por_correo(client)

    r = await _responde(client, invitada, invitacion["id"], action)
    inexistente = await _responde(client, invitada, str(uuid.uuid4()), action)

    assert r.status_code == 404, r.text
    assert inexistente.status_code == 404
    assert set(r.json()) == set(inexistente.json())


async def test_d2_d4_al_verificar_la_ve_y_la_acepta(client: AsyncClient):
    """
    Given: La misma invitación, y la cuenta verifica su correo
    When: Mira sus invitaciones, el listado y la ficha, y la acepta
    Then: Está en los tres sitios y queda aceptada
    """
    invitada, comp, invitacion, correo = await _invitada_por_correo(client)

    await _verifica(correo)

    mias = await _mis_invitaciones(client, invitada)
    assert [i["id"] for i in mias["invitations"]] == [invitacion["id"]]
    assert comp["id"] in await _listado(client, invitada)
    assert (await _ficha(client, invitada, comp))["my_pending_invitation"]["id"] == invitacion["id"]
    r = await _responde(client, invitada, invitacion["id"], "ACCEPT")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ACCEPTED"


async def test_d1_dirigida_a_la_cuenta_sin_verificar_sigue_igual(client: AsyncClient):
    """
    Given: Una invitación a la cuenta (por user_id), que no ha verificado su correo
    When: Mira sus invitaciones y la acepta
    Then: La ve y la acepta, como siempre
    """
    sufijo = uuid.uuid4().hex[:8]
    creador = await _jugador(client, f"org1-{sufijo}@test.com")
    invitada = await _jugador(client, f"cuenta-{sufijo}@test.com")
    comp = await _privada(client, creador)
    set_auth_cookies(client, creador["cookies"])
    enviada = await client.post(
        f"/api/v1/competitions/{comp['id']}/invitations",
        json={"invitee_user_id": invitada["user"]["id"]},
    )
    assert enviada.status_code == 201, enviada.text

    mias = await _mis_invitaciones(client, invitada)
    r = await _responde(client, invitada, enviada.json()["id"], "ACCEPT")

    assert [i["id"] for i in mias["invitations"]] == [enviada.json()["id"]]
    assert r.status_code == 200, r.text
