"""
Dispositivos fiables, fase 2: la lista y la limpieza (BE #737).

  #   caso                                                  | esperado
  ----|----------------------------------------------------|-------------------------------
  L1  un dispositivo con la sesión abierta                  | sale
  L2  uno que cerró sesión (su refresco revocado)           | no sale
  L3  uno con más de 24 h sin usarse                        | no sale: su sesión ya no vale
  L4  el dispositivo desde el que se mira                   | sale siempre, marcado como actual
  P1  un dispositivo sin usar desde hace más de 30 días     | la limpieza lo borra, y sus tokens
  P2  uno usado hace menos de 30 días (aunque revocado)     | se queda
  P3  un refresco caducado hace más de 7 días               | se borra
  P4  uno caducado hace menos de 7 días, o vigente          | se queda
  P5  la limpieza de otro usuario                           | no toca los demás
"""

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import status
from httpx import AsyncClient

from main import app as fastapi_app
from src.config.dependencies import get_db_session
from tests.conftest import sql_en_la_bd_de_test
from tests.integration.api.v1.test_dispositivos_fiables import (
    SAFARI_IPHONE,
    SAFARI_MAC,
    _cabeceras,
    _cloudflare,  # noqa: F401 - el secreto de Cloudflare, autouse
    _entra,
    _mis_dispositivos,
    _otro,
    _registra,
)

pytestmark = pytest.mark.asyncio


async def _envejece_dispositivo(device_id: str, horas: float) -> None:
    await sql_en_la_bd_de_test(
        "update user_devices set last_used_at = :t where id = :id",
        t=datetime.now() - timedelta(hours=horas),
        id=device_id,
    )


async def _dos_dispositivos(client: AsyncClient, prefijo: str):
    email = f"{prefijo}-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    iphone, mac = _otro(client), _otro(client)
    de_iphone = (await _entra(iphone, email, SAFARI_IPHONE, "red-casa")).json()["device_id"]
    de_mac = (await _entra(mac, email, SAFARI_MAC, "red-oficina")).json()["device_id"]
    return email, iphone, mac, de_iphone, de_mac


async def test_l1_l4_a_device_with_an_open_session_is_listed_and_the_current_one_marked(
    client: AsyncClient,
):
    """
    Given: Un iPhone y un Mac del mismo usuario, los dos con la sesión abierta
    When: El Mac mira su lista
    Then: Salen los dos, y el Mac marcado como el actual
    """
    _, _, mac, de_iphone, de_mac = await _dos_dispositivos(client, "l1")

    lista = await _mis_dispositivos(mac, SAFARI_MAC, "red-oficina")

    assert {d["id"] for d in lista} == {de_iphone, de_mac}
    assert [d["id"] for d in lista if d["is_current_device"]] == [de_mac]


async def test_l2_a_device_that_logged_out_is_not_listed(client: AsyncClient):
    """
    Given: Un iPhone que cerró sesión
    When: El Mac mira la lista
    Then: El iPhone no sale: no tiene ninguna sesión abierta
    """
    _, iphone, mac, _de_iphone, de_mac = await _dos_dispositivos(client, "l2")
    r = await iphone.post("/api/v1/auth/logout", json={}, headers=_cabeceras(SAFARI_IPHONE))
    assert r.status_code == status.HTTP_200_OK

    lista = await _mis_dispositivos(mac, SAFARI_MAC, "red-oficina")

    assert [d["id"] for d in lista] == [de_mac]


async def test_l3_a_device_unused_for_more_than_24h_is_not_listed(client: AsyncClient):
    """
    Given: Un iPhone que lleva 25 h sin usarse
    When: El Mac mira la lista
    Then: No sale: su sesión ya caducó por inactividad (BE #376)
    """
    _, _, mac, de_iphone, de_mac = await _dos_dispositivos(client, "l3")
    await _envejece_dispositivo(de_iphone, horas=25)

    lista = await _mis_dispositivos(mac, SAFARI_MAC, "red-oficina")

    assert [d["id"] for d in lista] == [de_mac]


async def test_p1_to_p5_cleanup_removes_old_devices_and_expired_tokens_only(client: AsyncClient):
    """
    Given: Dispositivos y refrescos de varias edades, de dos usuarios
    When: Pasa la limpieza
    Then: Se borran los dispositivos sin usar desde hace más de 30 días (con sus tokens) y
          los refrescos caducados hace más de 7 días; lo demás se queda
    """
    from src.config.limpieza_de_sesiones import LimpiezaDeSesiones

    _, _, _, viejo, reciente = await _dos_dispositivos(client, "p1")
    _, _, _, otro_viejo, _ = await _dos_dispositivos(client, "p5")
    await _envejece_dispositivo(viejo, horas=31 * 24)
    await _envejece_dispositivo(otro_viejo, horas=29 * 24)
    await sql_en_la_bd_de_test(
        "update user_devices set is_active = false where id = :id", id=otro_viejo
    )
    # Dos refrescos del dispositivo reciente: uno caducado hace 8 días, otro hace 6
    await sql_en_la_bd_de_test(
        "update refresh_tokens set expires_at = :t where device_id = :id",
        t=datetime.now() - timedelta(days=8),
        id=reciente,
    )
    cuantos_antes = (
        await sql_en_la_bd_de_test(
            "select count(*) from refresh_tokens where device_id = :id", id=reciente
        )
    ).scalar()
    # P5: sus tokens no han caducado; la limpieza no los toca aunque esté revocado
    del_otro_viejo_antes = (
        await sql_en_la_bd_de_test(
            "select count(*) from refresh_tokens where device_id = :id", id=otro_viejo
        )
    ).scalar()

    resumen = await LimpiezaDeSesiones(await _fabrica()).vuelta()

    quedan = {
        r[0]
        for r in (
            await sql_en_la_bd_de_test("select cast(id as text) from user_devices")
        ).fetchall()
    }
    assert viejo not in quedan, "P1: sin usar hace 31 días"
    assert reciente in quedan and otro_viejo in quedan, "P2/P5: menos de 30 días se quedan"
    assert (
        await sql_en_la_bd_de_test(
            "select count(*) from refresh_tokens where device_id = :id", id=viejo
        )
    ).scalar() == 0
    assert cuantos_antes >= 1
    assert (
        await sql_en_la_bd_de_test(
            "select count(*) from refresh_tokens where device_id = :id", id=reciente
        )
    ).scalar() == 0, "P3"
    assert del_otro_viejo_antes >= 1
    assert (
        await sql_en_la_bd_de_test(
            "select count(*) from refresh_tokens where device_id = :id", id=otro_viejo
        )
    ).scalar() == del_otro_viejo_antes, "P5: sus tokens sin caducar se quedan"
    assert resumen.dispositivos >= 1 and resumen.tokens >= 1


async def _fabrica():
    """Una fábrica de sesiones contra la base de datos del test, como la de la app."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    override = fastapi_app.dependency_overrides[get_db_session]
    async for sesion in override():
        return async_sessionmaker(sesion.bind, expire_on_commit=False)
    return None


async def test_p4_a_token_expired_less_than_7_days_ago_stays(client: AsyncClient):
    """
    Given: Un refresco caducado hace 6 días y otro vigente
    When: Pasa la limpieza
    Then: Los dos se quedan
    """
    from src.config.limpieza_de_sesiones import LimpiezaDeSesiones

    _, _, _, de_iphone, de_mac = await _dos_dispositivos(client, "p4")
    await sql_en_la_bd_de_test(
        "update refresh_tokens set expires_at = :t where device_id = :id",
        t=datetime.now() - timedelta(days=6),
        id=de_iphone,
    )

    await LimpiezaDeSesiones(await _fabrica()).vuelta()

    for dispositivo in (de_iphone, de_mac):
        assert (
            await sql_en_la_bd_de_test(
                "select count(*) from refresh_tokens where device_id = :id", id=dispositivo
            )
        ).scalar() == 1
