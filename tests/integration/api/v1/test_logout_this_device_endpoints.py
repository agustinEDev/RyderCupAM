"""
Cerrar sesión en un dispositivo no echa de los demás, de verdad (BE #376).

Dos inicios de sesión de la misma persona, cada uno con sus cookies, como el
ordenador de casa y el móvil en el campo. Sale en uno: el otro tiene que seguir
pudiendo renovar su sesión.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import _URL_DE_LA_BD_DE_TEST

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

CLAVE = "Sesi0nD1sp0s!tivo"


ORDENADOR = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/130.0 Safari/537.36"
MOVIL = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) Mobile/15E148 Safari/604.1"


async def _entra(client: AsyncClient, email: str, navegador: str) -> dict:
    """Un inicio de sesión desde un dispositivo nuevo: sin cookies previas.

    Sin cookie de dispositivo, el servidor lo reconoce por su huella (navegador
    e IP): con el mismo navegador serían el mismo dispositivo.
    """
    client.cookies.clear()
    respuesta = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE},
        headers={"User-Agent": navegador},
    )
    assert respuesta.status_code == 200, respuesta.text
    return dict(client.cookies)


def _usa(client: AsyncClient, cookies: dict) -> None:
    client.cookies.clear()
    for nombre, valor in cookies.items():
        client.cookies.set(nombre, valor)


async def test_salir_en_el_ordenador_no_echa_del_movil(client: AsyncClient):
    email = f"sesiones_{uuid4().hex[:8]}@example.com"
    alta = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": CLAVE, "first_name": "Ana", "last_name": "Golf"},
    )
    assert alta.status_code == 201, alta.text
    ordenador = await _entra(client, email, ORDENADOR)
    movil = await _entra(client, email, MOVIL)

    _usa(client, ordenador)
    salida = await client.post("/api/v1/auth/logout", json={}, headers={"User-Agent": ORDENADOR})
    assert salida.status_code == 200, salida.text

    _usa(client, movil)
    sigue = await client.post("/api/v1/auth/refresh-token", headers={"User-Agent": MOVIL})
    assert sigue.status_code == 200, sigue.text

    _usa(client, ordenador)
    cerrada = await client.post("/api/v1/auth/refresh-token", headers={"User-Agent": ORDENADOR})
    assert cerrada.status_code == 401, cerrada.text


async def test_veinticuatro_horas_sin_usar_la_sesion_caduca(client: AsyncClient):
    """OWASP A07: la inactividad la decide el servidor, por dispositivo."""
    email = f"inactiva_{uuid4().hex[:8]}@example.com"
    alta = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": CLAVE, "first_name": "Ana", "last_name": "Golf"},
    )
    assert alta.status_code == 201, alta.text
    movil = await _entra(client, email, MOVIL)
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE user_devices SET last_used_at = now() - interval '25 hours' "
                    "WHERE id = :id"
                ),
                {"id": movil["device_id"]},
            )
    finally:
        await engine.dispose()

    _usa(client, movil)
    caducada = await client.post("/api/v1/auth/refresh-token", headers={"User-Agent": MOVIL})

    assert caducada.status_code == 401, caducada.text


async def test_volver_a_entrar_no_resucita_un_token_viejo(client: AsyncClient):
    """CWE-613 (CodeRabbit en la #378): el login pone «último uso: ahora», y los
    tokens anteriores de un dispositivo inactivo no pueden volver a valer."""
    email = f"resucita_{uuid4().hex[:8]}@example.com"
    alta = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": CLAVE, "first_name": "Ana", "last_name": "Golf"},
    )
    assert alta.status_code == 201, alta.text
    viejo = await _entra(client, email, MOVIL)
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE user_devices SET last_used_at = now() - interval '25 hours' "
                    "WHERE id = :id"
                ),
                {"id": viejo["device_id"]},
            )
    finally:
        await engine.dispose()

    # Vuelve a entrar desde ese mismo dispositivo: su cookie incluida
    _usa(client, viejo)
    otra_vez = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE},
        headers={"User-Agent": MOVIL},
    )
    assert otra_vez.status_code == 200, otra_vez.text

    _usa(client, viejo)
    resucitado = await client.post("/api/v1/auth/refresh-token", headers={"User-Agent": MOVIL})

    assert resucitado.status_code == 401, resucitado.text
