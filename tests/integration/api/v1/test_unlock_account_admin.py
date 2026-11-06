"""
Desbloquear una cuenta es solo de administradores (hotfix 2.50.1).

Hasta la 2.50.0, `/unlock-account` solo pedía sesión: cualquier usuario podía quitar
el bloqueo por fallos de otra cuenta y seguir probando contraseñas contra ella
(auditoría OWASP de BE #732, A01/A07).

  #   caso                                        | esperado
  ----|--------------------------------------------|----------------------------------
  U1  un usuario normal desbloquea otra cuenta      | 403, y la cuenta sigue bloqueada
  U2  un usuario normal intenta su propia cuenta    | 403
  U3  un administrador desbloquea                   | 200, y la dueña ya puede entrar
"""

import uuid

import pytest
from httpx import AsyncClient

from src.config.rate_limit import limiter
from tests.conftest import create_admin_user, create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "ValidPassword123!"


@pytest.fixture(autouse=True)
def sin_cupo_por_minuto():
    """Para llegar al bloqueo sin chocar con el límite de intentos por minuto."""
    previous = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = previous


def _email(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:8]}@example.com"


async def _bloqueada(client: AsyncClient) -> dict:
    """Una cuenta bloqueada por fallos."""
    victima = await create_authenticated_user(client, _email("victima"), CLAVE, "Vic", "Tima")
    for i in range(10):
        await client.post(
            "/api/v1/auth/login",
            json={"email": victima["user"]["email"], "password": "WrongPassword123!"},
            headers={"X-Test-Client-ID": f"bloqueo-{i}"},
        )
    client.cookies.clear()
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": victima["user"]["email"], "password": CLAVE},
        headers={"X-Test-Client-ID": "comprueba"},
    )
    assert r.status_code == 423, r.text
    client.cookies.clear()
    return victima


async def _desbloquea(client: AsyncClient, quien: dict, user_id: str):
    set_auth_cookies(client, quien["cookies"])
    r = await client.post(
        "/api/v1/auth/unlock-account",
        # El contrato lo pide, pero la ruta pone siempre a quien llama
        json={"user_id": user_id, "unlocked_by_user_id": quien["user"]["id"]},
        headers={"X-CSRF-Token": quien["cookies"].get("csrf_token", "")},
    )
    client.cookies.clear()
    return r


async def _entra(client: AsyncClient, email: str):
    client.cookies.clear()
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE},
        headers={"X-Test-Client-ID": f"entra-{uuid.uuid4().hex[:6]}"},
    )
    client.cookies.clear()
    return r


async def test_u1_un_usuario_normal_no_desbloquea_otra_cuenta(client: AsyncClient):
    """
    Given: Una cuenta bloqueada por fallos, y otro usuario cualquiera con sesión
    When: Ese usuario la desbloquea
    Then: 403, y la cuenta sigue bloqueada
    """
    victima = await _bloqueada(client)
    atacante = await create_authenticated_user(client, _email("atacante"), CLAVE, "Ata", "Cante")

    r = await _desbloquea(client, atacante, victima["user"]["id"])

    assert r.status_code == 403, r.text
    assert (await _entra(client, victima["user"]["email"])).status_code == 423


async def test_u2_un_usuario_normal_tampoco_su_propia_cuenta(client: AsyncClient):
    """
    Given: Un usuario normal con sesión
    When: Pide desbloquear su propia cuenta
    Then: 403
    """
    yo = await create_authenticated_user(client, _email("yo"), CLAVE, "Yo", "Mismo")

    r = await _desbloquea(client, yo, yo["user"]["id"])

    assert r.status_code == 403, r.text


async def test_u3_un_administrador_desbloquea(client: AsyncClient):
    """
    Given: Una cuenta bloqueada por fallos y un administrador
    When: El administrador la desbloquea
    Then: 200, y la dueña ya puede entrar
    """
    victima = await _bloqueada(client)
    admin = await create_admin_user(client, _email("admin"), CLAVE, "Ad", "Min")

    r = await _desbloquea(client, admin, victima["user"]["id"])

    assert r.status_code == 200, r.text
    assert (await _entra(client, victima["user"]["email"])).status_code == 200
