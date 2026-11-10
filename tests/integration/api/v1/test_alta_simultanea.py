"""
Dos altas simultáneas con el mismo correo (R1, 7 nov 2026).

Las dos pasan la comprobación del correo antes de que ninguna guarde; la base de datos
para a la segunda con la restricción única. Esa segunda recibe el mismo 201 que si hubiera
llegado después (fase 3: el registro no dice si el correo existe), y no un 500.
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


async def test_r1_the_second_of_two_simultaneous_sign_ups_gets_the_same_201(
    client: AsyncClient, monkeypatch
):
    """
    Given: Una cuenta ya guardada con ese correo, y la comprobación del correo de la otra
           alta sin verla (como si las dos hubieran mirado a la vez)
    When: La segunda alta guarda y la base de datos la para
    Then: El mismo 201 que cualquier alta (fase 3: ya no hay 409), no 500; solo queda la
          primera cuenta
    """
    primera = await client.post("/api/v1/auth/register", json=ALTA)
    assert primera.status_code == 201
    real = UserFinder.by_email
    vistas = {"n": 0}

    async def no_lo_ve_la_primera_vez(self, email):
        vistas["n"] += 1
        return None if vistas["n"] == 1 else await real(self, email)

    monkeypatch.setattr(UserFinder, "by_email", no_lo_ve_la_primera_vez)

    r = await client.post("/api/v1/auth/register", json=ALTA)

    assert r.status_code == 201, r.text
    assert r.json()["id"] != primera.json()["id"]
    assert sorted(r.json()) == sorted(primera.json())


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
