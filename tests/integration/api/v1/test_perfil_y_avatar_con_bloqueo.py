"""
Perfil y avatar con un bloqueo o una cuenta desactivada (F-09, fase 3 del plan a 9).

  G2 el otro me bloqueó: su perfil y su avatar, 404 igual que una cuenta inexistente
     lo bloqueé yo: los sigo viendo (nombre, foto y «Desbloquear»; opción A, 10 nov)
  G3 cuenta desactivada: perfil y avatar, 404
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_admin_user, create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "P@ssw0rd123!"


async def _usuario(client: AsyncClient, nombre: str, avatar: int | None = None) -> dict:
    usuario = await create_authenticated_user(
        client, f"bq-{uuid.uuid4().hex[:8]}@test.com", CLAVE, nombre, "Bloqueo"
    )
    if avatar is not None:
        set_auth_cookies(client, usuario["cookies"])
        r = await client.post(
            "/api/v1/users/me/avatar/preset",
            json={"preset_id": avatar},
            headers={"X-CSRF-Token": usuario["cookies"].get("csrf_token", "")},
        )
        assert r.status_code == 200, r.text
        client.cookies.clear()
    return usuario


async def _bloquea(client: AsyncClient, quien: dict, a_quien: dict) -> None:
    set_auth_cookies(client, quien["cookies"])
    r = await client.post(
        f"/api/v1/friends/{a_quien['user']['id']}/block",
        headers={"X-CSRF-Token": quien["cookies"].get("csrf_token", "")},
    )
    assert r.status_code in (200, 201), r.text
    client.cookies.clear()


async def _pide(client: AsyncClient, quien: dict, ruta: str):
    client.cookies.clear()
    set_auth_cookies(client, quien["cookies"])
    r = await client.get(ruta)
    client.cookies.clear()
    return r


def _rutas(de: str) -> dict[str, str]:
    return {
        "perfil": f"/api/v1/users/{de}/profile",
        "avatar": f"/api/v1/users/{de}/avatar",
    }


@pytest.mark.parametrize("que", ["perfil", "avatar"])
async def test_g2_si_me_bloqueo_es_como_si_no_existiera(client: AsyncClient, que: str):
    """
    Given: Luis (con avatar) me bloqueó
    When: Pido su perfil o su avatar
    Then: 404, con el mismo cuerpo que para un id que no existe
    """
    yo = await _usuario(client, "Ana")
    el = await _usuario(client, "Luis", avatar=4)
    await _bloquea(client, el, yo)

    r = await _pide(client, yo, _rutas(el["user"]["id"])[que])
    inexistente_id = str(uuid.uuid4())
    inexistente = await _pide(client, yo, _rutas(inexistente_id)[que])

    assert r.status_code == 404, r.text
    assert inexistente.status_code == 404
    assert r.json()["detail"].replace(el["user"]["id"], "X") == inexistente.json()[
        "detail"
    ].replace(inexistente_id, "X")


@pytest.mark.parametrize("que", ["perfil", "avatar"])
async def test_g2_si_lo_bloquee_yo_lo_sigo_viendo(client: AsyncClient, que: str):
    """
    Given: Bloqueé a Luis (con avatar)
    When: Pido su perfil o su avatar
    Then: 200: desde su perfil se desbloquea
    """
    yo = await _usuario(client, "Ana")
    el = await _usuario(client, "Luis", avatar=4)
    await _bloquea(client, yo, el)

    r = await _pide(client, yo, _rutas(el["user"]["id"])[que])

    assert r.status_code == 200, r.text
    if que == "perfil":
        assert r.json()["blocked_by_me"] is True


@pytest.mark.parametrize("que", ["perfil", "avatar"])
async def test_g2_sin_bloqueo_se_ve(client: AsyncClient, que: str):
    """
    Given: Ningún bloqueo con Luis (con avatar)
    When: Pido su perfil o su avatar
    Then: 200
    """
    yo = await _usuario(client, "Ana")
    el = await _usuario(client, "Luis", avatar=4)

    r = await _pide(client, yo, _rutas(el["user"]["id"])[que])

    assert r.status_code == 200, r.text


@pytest.mark.parametrize("que", ["perfil", "avatar"])
async def test_g3_cuenta_desactivada_da_404(client: AsyncClient, que: str):
    """
    Given: La cuenta de Luis (con avatar) desactivada por un administrador
    When: Pido su perfil o su avatar
    Then: 404
    """
    yo = await _usuario(client, "Ana")
    el = await _usuario(client, "Luis", avatar=4)
    admin = await create_admin_user(
        client, f"bq-admin-{uuid.uuid4().hex[:8]}@test.com", CLAVE, "Admin", "Test"
    )
    client.cookies.clear()
    client.cookies.update(admin["cookies"])
    r = await client.put(
        f"/api/v1/admin/users/{el['user']['id']}/active",
        json={"is_active": False},
        headers={"X-CSRF-Token": admin["cookies"].get("csrf_token", "")},
    )
    assert r.status_code == 204, r.text
    client.cookies.clear()

    r = await _pide(client, yo, _rutas(el["user"]["id"])[que])

    assert r.status_code == 404, r.text
