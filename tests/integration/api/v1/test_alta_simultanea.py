"""
Dos altas simultáneas con el mismo correo (R1, 7 nov 2026).

Las dos pasan la comprobación del correo antes de que ninguna guarde; la base de datos
para a la segunda con la restricción única. Esa segunda recibe 409 «ya registrado», como
si hubiera llegado después, y no un 500.
"""

import pytest
from httpx import AsyncClient

from src.modules.user.domain.services.user_finder import UserFinder

pytestmark = pytest.mark.asyncio

ALTA = {
    "email": "r1@example.com",
    "password": "V@l1dP@ss123!",
    "first_name": "Ana",
    "last_name": "Lopez",
    "accept_terms": True,
}


async def test_r1_the_second_of_two_simultaneous_sign_ups_gets_409(
    client: AsyncClient, monkeypatch
):
    """
    Given: Una cuenta ya guardada con ese correo, y la comprobación del correo de la otra
           alta sin verla (como si las dos hubieran mirado a la vez)
    When: La segunda alta guarda
    Then: 409 con el texto de «ya registrado», no 500
    """
    assert (await client.post("/api/v1/auth/register", json=ALTA)).status_code == 201

    async def no_lo_ve(self, email):
        return None

    monkeypatch.setattr(UserFinder, "by_email", no_lo_ve)

    r = await client.post("/api/v1/auth/register", json=ALTA)

    assert r.status_code == 409, r.text
    assert "ya está registrado" in r.json()["detail"]


async def test_r1_another_constraint_is_not_hidden_as_already_registered(client: AsyncClient):
    """
    Given: Un alta que choca con otra restricción de la base de datos (no la del correo)
    When: Se registra
    Then: No sale «ya registrado»: un fallo distinto no se esconde bajo un 409
    """
    from sqlalchemy.exc import IntegrityError

    from main import app
    from src.config.dependencies import get_register_user_use_case

    class _OtraError(Exception):
        constraint_name = "terms_acceptances_user_id_fkey"

    original = Exception("violates foreign key constraint")
    original.__cause__ = _OtraError()

    class _Falla:
        async def execute(self, _datos):
            raise IntegrityError("INSERT", {}, original)

    app.dependency_overrides[get_register_user_use_case] = _Falla
    try:
        r = await client.post(
            "/api/v1/auth/register", json={**ALTA, "email": "r1.otra@example.com"}
        )
    finally:
        app.dependency_overrides.pop(get_register_user_use_case, None)

    assert r.status_code == 500
