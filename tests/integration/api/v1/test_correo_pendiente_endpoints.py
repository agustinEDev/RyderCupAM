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


async def _pide(client: AsyncClient, correos, viejo=VIEJO, nuevo=NUEVO):
    datos = await create_authenticated_user(client, viejo, CLAVE, "Ana", "Lopez")
    cabecera = {"Cookie": f"access_token={datos['token']}"}
    r = await client.patch(
        "/api/v1/users/security",
        json={"current_password": CLAVE, "new_email": nuevo},
        headers=cabecera,
    )
    # El token, del correo (en la BD solo está su hash)
    return (
        r,
        cabecera,
        correos.send_email_change_confirmation.await_args.kwargs["token"],
    )


async def _confirma(client, cabecera, token):
    return await client.post(
        "/api/v1/users/me/email-change/confirm", json={"token": token}, headers=cabecera
    )


async def test_i1_asking_keeps_the_old_email_with_the_new_one_pending(
    client: AsyncClient, mock_external_services
):
    r, cabecera, _token = await _pide(client, mock_external_services)

    assert r.status_code == 200
    assert r.json()["user"]["email"] == VIEJO
    assert r.json()["user"]["pending_email"] == NUEVO
    yo = await client.get("/api/v1/auth/current-user", headers=cabecera)
    assert yo.json()["email"] == VIEJO
    assert yo.json()["pending_email"] == NUEVO


async def test_i2_confirming_switches_the_email_and_it_signs_in(
    client: AsyncClient, mock_external_services
):
    _r, cabecera, token = await _pide(
        client, mock_external_services, "i2.viejo@example.com", "i2.nuevo@example.com"
    )

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


async def test_i3_without_a_session_nobody_confirms(client: AsyncClient, mock_external_services):
    _r, _cabecera, token = await _pide(
        client, mock_external_services, "i3.viejo@example.com", "i3.nuevo@example.com"
    )
    client.cookies.clear()

    r = await client.post("/api/v1/users/me/email-change/confirm", json={"token": token})

    assert r.status_code == 401
    filas = await _sql("select email from users where email = :e", {"e": "i3.viejo@example.com"})
    assert filas == [("i3.viejo@example.com",)]


async def test_i4_a_late_confirmation_is_refused_and_cancels(
    client: AsyncClient, mock_external_services
):
    _r, cabecera, token = await _pide(
        client, mock_external_services, "i4.viejo@example.com", "i4.nuevo@example.com"
    )
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


async def test_i5_another_token_is_refused(client: AsyncClient, mock_external_services):
    _r, cabecera, _token = await _pide(
        client, mock_external_services, "i5.viejo@example.com", "i5.nuevo@example.com"
    )

    r = await _confirma(client, cabecera, "no-es-el-token")

    assert r.status_code == 400
    assert r.json()["error_code"] == "EMAIL_CHANGE_INVALID"


async def test_i6_an_address_taken_meanwhile_is_refused(
    client: AsyncClient, mock_external_services
):
    _r, cabecera, token = await _pide(
        client, mock_external_services, "i6.viejo@example.com", "i6.nuevo@example.com"
    )
    await create_authenticated_user(client, "i6.nuevo@example.com", CLAVE, "Otra", "Persona")

    r = await _confirma(client, cabecera, token)

    assert r.status_code == 409
    assert r.json()["error_code"] == "EMAIL_ALREADY_IN_USE"
    filas = await _sql(
        "select pending_email from users where email = :e", {"e": "i6.viejo@example.com"}
    )
    assert filas == [(None,)]


async def test_i7_cancelling_leaves_nothing_pending(client: AsyncClient, mock_external_services):
    _r, cabecera, token = await _pide(
        client, mock_external_services, "i7.viejo@example.com", "i7.nuevo@example.com"
    )

    r = await client.delete("/api/v1/users/me/email-change", headers=cabecera)

    assert r.status_code == 200
    assert r.json()["pending_email"] is None
    assert (await _confirma(client, cabecera, token)).status_code == 400


async def test_another_accounts_session_cannot_confirm_my_change(
    client: AsyncClient, mock_external_services
):
    """
    Given: Ana con un cambio pendiente, y Luis con su sesión y el token de Ana
    When: Luis confirma con ese token
    Then: 400 EMAIL_CHANGE_INVALID: el token solo vale con la sesión de su cuenta; Ana
          sigue igual, con su pendiente
    """
    _r, _ana, token = await _pide(
        client, mock_external_services, "ana.dueña@example.com", "ana.nuevo@example.com"
    )
    luis = await create_authenticated_user(client, "luis.otro@example.com", CLAVE, "Luis", "Otro")

    r = await _confirma(client, {"Cookie": f"access_token={luis['token']}"}, token)

    assert r.status_code == 400
    assert r.json()["error_code"] == "EMAIL_CHANGE_INVALID"
    filas = await _sql(
        "select email, pending_email from users where email = :e", {"e": "ana.dueña@example.com"}
    )
    assert filas == [("ana.dueña@example.com", "ana.nuevo@example.com")]


async def test_a_last_moment_duplicate_is_409_and_cancels(
    client: AsyncClient, mock_external_services, monkeypatch
):
    """
    Given: Un cambio pendiente a un correo que otra cuenta ya tiene, y la comprobación
           de «ocupado» que no lo ve (como si lo ocupara justo después)
    When: Se confirma: salta la restricción única de la BD al guardar
    Then: 409 EMAIL_ALREADY_IN_USE y el pendiente anulado: la sesión de la BD sigue
          sirviendo tras el fallo (CodeRabbit en #752)
    """
    from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
        SQLAlchemyUserRepository,
    )

    _r, cabecera, token = await _pide(
        client, mock_external_services, "ultimo.viejo@example.com", "ultimo.nuevo@example.com"
    )
    await create_authenticated_user(client, "ultimo.nuevo@example.com", CLAVE, "Otra", "Persona")
    original = SQLAlchemyUserRepository.find_by_email

    async def no_lo_ve(self, email):
        if str(email.value) == "ultimo.nuevo@example.com":
            return None
        return await original(self, email)

    monkeypatch.setattr(SQLAlchemyUserRepository, "find_by_email", no_lo_ve)

    r = await _confirma(client, cabecera, token)

    assert r.status_code == 409
    assert r.json()["error_code"] == "EMAIL_ALREADY_IN_USE"
    filas = await _sql(
        "select email, pending_email from users where email = :e", {"e": "ultimo.viejo@example.com"}
    )
    assert filas == [("ultimo.viejo@example.com", None)]
