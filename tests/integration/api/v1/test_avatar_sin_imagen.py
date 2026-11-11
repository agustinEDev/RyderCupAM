"""
El avatar sin imagen responde 204, igual en todos los casos (2.59.0, BE #793).

Hasta la 2.58.0, sin avatar era un 404 con «has no avatar set» y un bloqueo un 404 con
«not found»: el texto delataba el bloqueo, y cada persona sin avatar costaba un 404 que
el navegador no guarda. Ahora:

  A1 avatar predefinido: 200 con la imagen
  A2 foto subida: 200 con la imagen
  A3 sin avatar: 204 sin cuerpo
  A4 su dueño me bloqueó: 204
  A5 un id que no existe: 204
  A6 la foto activa ya no existe: 204
  A7 A3-A6 no se distinguen: mismo código, mismas cabeceras, cuerpo vacío
  A8 el 204 lleva Cache-Control: no-store
  A9 sin sesión: 401
  A10 un id mal formado: 422
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import create_authenticated_user, set_auth_cookies, sql_en_la_bd_de_test

pytestmark = pytest.mark.asyncio

CLAVE = "P@ssw0rd123!"
# Lo que cambia en cada respuesta sin decir nada del caso: la hora y los ids de petición
CABECERAS_DE_CADA_PETICION = {"date", "x-correlation-id", "x-request-id", "x-process-time"}


async def _usuario(client: AsyncClient, nombre: str, avatar: int | None = None) -> dict:
    """Un usuario y, si se pide, un avatar predefinido."""
    usuario = await create_authenticated_user(
        client, f"av-{uuid.uuid4().hex[:8]}@test.com", CLAVE, nombre, "Avatar"
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


async def _avatar(client: AsyncClient, quien: dict, de: str):
    """GET del avatar de `de` con la sesión de `quien`."""
    client.cookies.clear()
    set_auth_cookies(client, quien["cookies"])
    r = await client.get(f"/api/v1/users/{de}/avatar")
    client.cookies.clear()
    return r


def _huella(r) -> tuple:
    """Lo que ve quien pide: código, cabeceras (sin las de cada petición) y cuerpo."""
    cabeceras = sorted(
        (k.lower(), v) for k, v in r.headers.items() if k.lower() not in CABECERAS_DE_CADA_PETICION
    )
    return r.status_code, tuple(cabeceras), r.content


async def test_a1_a2_con_avatar_la_imagen(client: AsyncClient):
    """
    Given: Luis con un avatar predefinido
    When: Ana pide su avatar
    Then: 200 con la imagen
    """
    yo = await _usuario(client, "Ana")
    el = await _usuario(client, "Luis", avatar=4)

    r = await _avatar(client, yo, el["user"]["id"])

    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/")
    assert len(r.content) > 0


async def test_a3_a7_los_cuatro_casos_sin_imagen_son_el_mismo_204(client: AsyncClient):
    """
    Given: Luis sin avatar; Bea (con avatar) que me bloqueó; un id de nadie; y Carla, cuya
           foto activa ya no existe
    When: Ana pide los cuatro avatares
    Then: 204 sin cuerpo, sin texto, con no-store, y las cuatro respuestas iguales
    """
    yo = await _usuario(client, "Ana")
    sin_avatar = await _usuario(client, "Luis")
    me_bloqueo = await _usuario(client, "Bea", avatar=2)
    set_auth_cookies(client, me_bloqueo["cookies"])
    r = await client.post(
        f"/api/v1/friends/{yo['user']['id']}/block",
        headers={"X-CSRF-Token": me_bloqueo["cookies"].get("csrf_token", "")},
    )
    assert r.status_code in (200, 201), r.text
    client.cookies.clear()
    foto_perdida = await _usuario(client, "Carla")
    # Lo que deja borrar la foto activa: la clave ajena la pone a NULL (ON DELETE SET
    # NULL) y el origen sigue en UPLOAD
    await sql_en_la_bd_de_test(
        "update users set avatar_source = 'UPLOAD', active_avatar_upload_id = NULL where id = :i",
        i=foto_perdida["user"]["id"],
    )

    respuestas = [
        await _avatar(client, yo, sin_avatar["user"]["id"]),
        await _avatar(client, yo, me_bloqueo["user"]["id"]),
        await _avatar(client, yo, str(uuid.uuid4())),
        await _avatar(client, yo, foto_perdida["user"]["id"]),
    ]

    for r in respuestas:
        assert r.status_code == 204, r.text
        assert r.content == b""
        assert r.headers.get("cache-control") == "no-store"
    huellas = {_huella(r) for r in respuestas}
    assert len(huellas) == 1, huellas


async def test_a9_sin_sesion_401(client: AsyncClient):
    """
    Given: Nadie dentro
    When: Se pide un avatar
    Then: 401, como hoy
    """
    client.cookies.clear()

    r = await client.get(f"/api/v1/users/{uuid.uuid4()}/avatar")

    assert r.status_code == 401


async def test_a10_un_id_mal_formado_422(client: AsyncClient):
    """
    Given: Una sesión
    When: Se pide el avatar de algo que no es un uuid
    Then: 422, como hoy
    """
    yo = await _usuario(client, "Ana")

    r = await _avatar(client, yo, "no-es-un-uuid")

    assert r.status_code == 422
