"""
El cambio de correo pendiente, por la API (#749).

  #   Caso                                         | Respuesta
  ----|----------------------------------------------|--------------------------------
  I1  pedir el cambio                              | 200, sigue el correo de antes,
                                                   |   pending_email el nuevo (también
                                                   |   en current-user)
  I2  confirmar con sesión y su token              | 200, el correo es el nuevo y se
                                                   |   entra con él (con el viejo, no)
  I3  confirmar sin sesión                         | 401: un desconocido no confirma
  I4  confirmar pasadas las 24 h                   | 400 EMAIL_CHANGE_EXPIRED, anulado
  I5  otro token                                   | 400 EMAIL_CHANGE_INVALID
  I6  el nuevo lo usa otra cuenta al confirmar     | 409 EMAIL_ALREADY_IN_USE, anulado
  I7  anular                                       | 200, sin pendiente
"""

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user
from tests.integration.api.v1.test_terms_acceptance_endpoints import _sql

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"
VIEJO = "pendiente.viejo@example.com"
NUEVO = "pendiente.nuevo@example.com"


async def _pide(client: AsyncClient, viejo=VIEJO, nuevo=NUEVO):
    datos = await create_authenticated_user(client, viejo, CLAVE, "Ana", "Lopez")
    cabecera = {"Authorization": f"Bearer {datos['token']}"}
    r = await client.patch(
        "/api/v1/users/security",
        json={"current_password": CLAVE, "new_email": nuevo},
        headers=cabecera,
    )
    filas = await _sql("select pending_email_token from users where email = :e", {"e": viejo})
    return r, cabecera, filas[0][0]


async def _confirma(client, cabecera, token):
    return await client.post(
        "/api/v1/users/me/email-change/confirm", json={"token": token}, headers=cabecera
    )


async def test_i1_asking_keeps_the_old_email_with_the_new_one_pending(client: AsyncClient):
    r, cabecera, _token = await _pide(client)

    assert r.status_code == 200
    assert r.json()["user"]["email"] == VIEJO
    assert r.json()["user"]["pending_email"] == NUEVO
    yo = await client.get("/api/v1/auth/current-user", headers=cabecera)
    assert yo.json()["email"] == VIEJO
    assert yo.json()["pending_email"] == NUEVO


async def test_i2_confirming_switches_the_email_and_it_signs_in(client: AsyncClient):
    _r, cabecera, token = await _pide(client, "i2.viejo@example.com", "i2.nuevo@example.com")

    r = await _confirma(client, cabecera, token)

    assert r.status_code == 200
    assert r.json()["email"] == "i2.nuevo@example.com"
    assert r.json()["email_verified"] is True
    assert r.json()["pending_email"] is None
    client.cookies.clear()
    nuevo = await client.post(
        "/api/v1/auth/login",
        json={"email": "i2.nuevo@example.com", "password": CLAVE},
        headers={"X-Test-Client-ID": "i2-nuevo"},
    )
    viejo = await client.post(
        "/api/v1/auth/login",
        json={"email": "i2.viejo@example.com", "password": CLAVE},
        headers={"X-Test-Client-ID": "i2-viejo"},
    )
    assert nuevo.status_code == 200
    assert viejo.status_code == 401


async def test_i3_without_a_session_nobody_confirms(client: AsyncClient):
    _r, _cabecera, token = await _pide(client, "i3.viejo@example.com", "i3.nuevo@example.com")
    client.cookies.clear()

    r = await client.post("/api/v1/users/me/email-change/confirm", json={"token": token})

    assert r.status_code == 401
    filas = await _sql("select email from users where email = :e", {"e": "i3.viejo@example.com"})
    assert filas == [("i3.viejo@example.com",)]


async def test_i4_a_late_confirmation_is_refused_and_cancels(client: AsyncClient):
    _r, cabecera, token = await _pide(client, "i4.viejo@example.com", "i4.nuevo@example.com")
    await _sql(
        "update users set pending_email_expires_at = now() - interval '1 hour' where email = :e",
        {"e": "i4.viejo@example.com"},
    )

    r = await _confirma(client, cabecera, token)

    assert r.status_code == 400
    assert r.json()["error_code"] == "EMAIL_CHANGE_EXPIRED"
    filas = await _sql(
        "select email, pending_email from users where email = :e", {"e": "i4.viejo@example.com"}
    )
    assert filas == [("i4.viejo@example.com", None)]


async def test_i5_another_token_is_refused(client: AsyncClient):
    _r, cabecera, _token = await _pide(client, "i5.viejo@example.com", "i5.nuevo@example.com")

    r = await _confirma(client, cabecera, "no-es-el-token")

    assert r.status_code == 400
    assert r.json()["error_code"] == "EMAIL_CHANGE_INVALID"


async def test_i6_an_address_taken_meanwhile_is_refused(client: AsyncClient):
    _r, cabecera, token = await _pide(client, "i6.viejo@example.com", "i6.nuevo@example.com")
    await create_authenticated_user(client, "i6.nuevo@example.com", CLAVE, "Otra", "Persona")

    r = await _confirma(client, cabecera, token)

    assert r.status_code == 409
    assert r.json()["error_code"] == "EMAIL_ALREADY_IN_USE"
    filas = await _sql(
        "select pending_email from users where email = :e", {"e": "i6.viejo@example.com"}
    )
    assert filas == [(None,)]


async def test_i7_cancelling_leaves_nothing_pending(client: AsyncClient):
    _r, cabecera, token = await _pide(client, "i7.viejo@example.com", "i7.nuevo@example.com")

    r = await client.delete("/api/v1/users/me/email-change", headers=cabecera)

    assert r.status_code == 200
    assert r.json()["pending_email"] is None
    assert (await _confirma(client, cabecera, token)).status_code == 400
