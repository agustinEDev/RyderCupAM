"""
`GET /users/search?email=` (F-01b, fase 3 del plan a 9).

  F1 límite propio: 20 por hora y usuario; la 21.ª, 429 TOO_MANY_USER_SEARCHES.
     Cada usuario, su contador; buscar solo por nombre no lo gasta
  F2 una cuenta desactivada responde lo mismo que un correo que no existe
  F3 el resultado sigue igual (id y nombre)
"""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient, Response

from tests.conftest import create_admin_user, create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "P@ssw0rd123!"
LIMITE = 20


async def _usuario(client: AsyncClient, nombre: str = "Busca") -> dict:
    email = f"busca-{uuid.uuid4().hex[:8]}@test.com"
    return await create_authenticated_user(client, email, CLAVE, nombre, "Correo")


async def _busca(client: AsyncClient, quien: dict, **params) -> Response:
    client.cookies.clear()
    set_auth_cookies(client, quien["cookies"])
    r = await client.get("/api/v1/users/search", params=params)
    client.cookies.clear()
    return r


async def _agota(client: AsyncClient, quien: dict) -> None:
    for i in range(LIMITE):
        r = await _busca(client, quien, email=f"nadie-{i}@test.com")
        assert r.status_code == status.HTTP_404_NOT_FOUND, f"{i + 1}: {r.status_code} {r.text}"


async def test_f1_la_vigesimo_primera_busqueda_por_correo_en_la_hora_da_429(client: AsyncClient):
    """
    Given: Un usuario que ya buscó 20 correos esta hora
    When: Busca el 21.º
    Then: 429 con error_code TOO_MANY_USER_SEARCHES; las 20 primeras respondieron
    """
    yo = await _usuario(client)
    await _agota(client, yo)

    r = await _busca(client, yo, email="otro@test.com")

    assert r.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert r.json()["error_code"] == "TOO_MANY_USER_SEARCHES"


async def test_f1_el_429_no_dice_si_el_correo_existe(client: AsyncClient):
    """
    Given: Un usuario con el cupo agotado
    When: Busca un correo que SÍ existe
    Then: El mismo 429, sin el resultado
    """
    yo = await _usuario(client)
    otro = await _usuario(client, "Existe")
    await _agota(client, yo)

    r = await _busca(client, yo, email=otro["user"]["email"])

    assert r.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "user_id" not in r.json()


async def test_f1_cada_usuario_tiene_su_contador(client: AsyncClient):
    """
    Given: Un usuario con el cupo agotado
    When: Otro usuario busca un correo
    Then: A ese otro le responde con normalidad
    """
    yo = await _usuario(client)
    otro = await _usuario(client, "Otro")
    await _agota(client, yo)

    r = await _busca(client, otro, email="nadie@test.com")

    assert r.status_code == status.HTTP_404_NOT_FOUND


async def test_f1_buscar_por_nombre_no_gasta_el_cupo_del_correo(client: AsyncClient):
    """
    Given: Un usuario con el cupo del correo agotado
    When: Busca por nombre completo, sin correo
    Then: No le da 429
    """
    yo = await _usuario(client)
    await _agota(client, yo)

    r = await _busca(client, yo, full_name="Nadie Ninguno")

    assert r.status_code == status.HTTP_404_NOT_FOUND


async def test_f2_una_cuenta_desactivada_es_como_un_correo_que_no_existe(client: AsyncClient):
    """
    Given: Una cuenta desactivada por un administrador
    When: Alguien busca su correo, y otro que no existe
    Then: Los dos 404, con el mismo mensaje (salvo el correo que se buscó)
    """
    yo = await _usuario(client)
    baja = await _usuario(client, "Baja")
    admin = await create_admin_user(
        client, f"admin-{uuid.uuid4().hex[:8]}@test.com", CLAVE, "Admin", "Test"
    )
    client.cookies.clear()
    client.cookies.update(admin["cookies"])
    r = await client.put(
        f"/api/v1/admin/users/{baja['user']['id']}/active",
        json={"is_active": False},
        headers={"X-CSRF-Token": admin["cookies"].get("csrf_token", "")},
    )
    assert r.status_code == status.HTTP_204_NO_CONTENT, r.text
    client.cookies.clear()

    correo_baja = baja["user"]["email"]
    desactivada = await _busca(client, yo, email=correo_baja)
    inexistente = await _busca(client, yo, email="no-existe@test.com")

    assert desactivada.status_code == inexistente.status_code == status.HTTP_404_NOT_FOUND
    assert desactivada.json()["detail"].replace(correo_baja, "X") == inexistente.json()[
        "detail"
    ].replace("no-existe@test.com", "X")


async def test_f3_el_resultado_sigue_igual(client: AsyncClient):
    """
    Given: Una cuenta activa
    When: Se busca por su correo
    Then: 200 con su id y su nombre, como siempre
    """
    yo = await _usuario(client)
    otro = await _usuario(client, "Encontrado")

    r = await _busca(client, yo, email=otro["user"]["email"])

    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["user_id"] == otro["user"]["id"]
    assert r.json()["full_name"] == "Encontrado Correo"
