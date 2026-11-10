"""
El reenvío del enlace de verificación por la API (fase 3, revisión; decidido por Agustín).

  #   Caso                                             | Resultado
  ----|-------------------------------------------------|-------------------------------
  T1  la toma: alguien registra el correo de otro y   | 200 genérico, ningún correo
      pide reenviar sin sesión, por correo             |
  S1  con sesión, su propio correo (el aviso de hoy)   | 200 y sale el enlace
  S2  con sesión, el correo de otra cuenta             | 200 genérico, ningún correo
  L1  sin sesión, con el enlace caducado               | 200; sale uno nuevo que verifica
                                                       |   y el caducado ya no sirve
  L2  sin sesión, con un token que no es               | 200 igual, ningún correo
  L3  4.ª vez con el mismo enlace desde la misma red   | 429
"""

import uuid

import pytest
from httpx import AsyncClient

from src.config.aviso_en_segundo_plano import espera_los_avisos_pendientes
from tests.conftest import sql_en_la_bd_de_test, token_de_verificacion_enviado

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"


def _correo() -> str:
    return f"rv-{uuid.uuid4().hex[:10]}@example.com"


def _red(nombre: str) -> dict:
    return {"X-Test-Client-ID": f"{nombre}-{uuid.uuid4().hex[:6]}"}


async def _registra(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": CLAVE,
            "first_name": "Ana",
            "last_name": "Lopez",
            "accept_terms": True,
        },
        headers=_red("alta"),
    )
    assert r.status_code == 201, r.text
    client.cookies.clear()
    return await token_de_verificacion_enviado(email)


def _enviados(mock, email: str) -> int:
    return sum(
        1 for c in mock.send_verification_email.await_args_list if c.kwargs["to_email"] == email
    )


async def _reenvia_por_correo(client: AsyncClient, email: str, headers=None):
    r = await client.post(
        "/api/v1/auth/resend-verification", json={"email": email}, headers=headers or {}
    )
    await espera_los_avisos_pendientes(tope_s=10)
    return r


async def _reenvia_con_enlace(client: AsyncClient, token: str, red: dict):
    r = await client.post(
        "/api/v1/auth/resend-verification-link", json={"token": token}, headers=red
    )
    await espera_los_avisos_pendientes(tope_s=10)
    return r


async def test_t1_resending_without_a_session_by_email_sends_nothing(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cuenta sin verificar (pudo crearla cualquiera con el correo de otro)
    When: Sin sesión, se pide reenviar por correo
    Then: 200 genérico y ningún correo: el correo ajeno no basta
    """
    email = _correo()
    await _registra(client, email)

    r = await _reenvia_por_correo(client, email)

    assert r.status_code == 200
    assert _enviados(mock_external_services, email) == 1  # solo el del alta


@pytest.mark.parametrize("de_quien", ["suyo", "de otra cuenta"])
async def test_s1_s2_with_a_session_only_its_own_email(
    client: AsyncClient, mock_external_services, de_quien
):
    """
    Given: Una cuenta sin verificar con sesión (el aviso de la app)
    When: Pide reenviar con su correo, o con el de otra cuenta sin verificar
    Then: Con el suyo sale el enlace; con el de otra, 200 y nada
    """
    email, otro = _correo(), _correo()
    await _registra(client, email)
    await _registra(client, otro)
    entra = await client.post("/api/v1/auth/login", json={"email": email, "password": CLAVE})
    assert entra.status_code == 200, entra.text
    pedido = email if de_quien == "suyo" else otro

    r = await _reenvia_por_correo(
        client, pedido, headers={"X-CSRF-Token": entra.json()["csrf_token"]}
    )

    assert r.status_code == 200, r.text
    assert r.json()["email"] == pedido
    assert _enviados(mock_external_services, pedido) == (2 if de_quien == "suyo" else 1)


async def test_l1_an_expired_link_brings_a_new_one(client: AsyncClient, mock_external_services):
    """
    Given: Una cuenta con su enlace caducado
    When: Sin sesión, pide otro con él
    Then: 200; sale uno nuevo que verifica; el caducado ya no sirve
    """
    email = _correo()
    viejo = await _registra(client, email)
    await sql_en_la_bd_de_test(
        "update users set verification_token_expires_at = now() - interval '1 minute' "
        "where email = :e",
        e=email,
    )

    r = await _reenvia_con_enlace(client, viejo, _red("casa"))

    assert r.status_code == 200, r.text
    nuevo = await token_de_verificacion_enviado(email)
    assert nuevo != viejo
    otra_vez = await client.post("/api/v1/auth/verify-email", json={"token": viejo})
    assert otra_vez.status_code == 400
    assert otra_vez.json().get("error_code") != "VERIFICATION_TOKEN_EXPIRED"
    verifica = await client.post("/api/v1/auth/verify-email", json={"token": nuevo})
    assert verifica.status_code == 200, verifica.text


async def test_l2_a_wrong_token_answers_the_same_and_sends_nothing(
    client: AsyncClient, mock_external_services
):
    """
    Given: Una cuenta con su enlace caducado
    When: Sin sesión, se pide otro con un token que no es
    Then: La misma respuesta que con el bueno, y ningún correo
    """
    email = _correo()
    viejo = await _registra(client, email)
    await sql_en_la_bd_de_test(
        "update users set verification_token_expires_at = now() - interval '1 minute' "
        "where email = :e",
        e=email,
    )

    malo = await _reenvia_con_enlace(client, "token-que-no-es-" + uuid.uuid4().hex, _red("x"))
    bueno = await _reenvia_con_enlace(client, viejo, _red("y"))

    assert malo.status_code == bueno.status_code == 200
    assert malo.json() == bueno.json()
    assert _enviados(mock_external_services, email) == 2  # el del alta y el del bueno


async def test_l3_three_per_hour_per_link_and_network(client: AsyncClient):
    """
    Given: Un enlace (exista o no)
    When: Se pide otro con él 4 veces desde la misma red, y una desde otra
    Then: La 4.ª de esa red, 429; desde la otra, 200
    """
    token = "token-" + uuid.uuid4().hex
    red = _red("club")

    estados = [(await _reenvia_con_enlace(client, token, red)).status_code for _ in range(4)]
    otra = await _reenvia_con_enlace(client, token, _red("casa"))

    assert estados == [200, 200, 200, 429]
    assert otra.status_code == 200
