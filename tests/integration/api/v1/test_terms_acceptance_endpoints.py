"""
Aceptación de los Términos por la API (B1-B7), contra PostgreSQL.

- B1/B2: el registro exige `accept_terms: true` y guarda versión y fecha.
- B3: el alta con Google entra sin aceptar.
- B4: current-user (y el `user` de login) dicen si tiene aceptada la vigente.
- B5: POST /api/v1/users/me/accept-terms, idempotente.
- B6: sin aceptar, 403 TERMS_NOT_ACCEPTED en toda ruta con sesión salvo las exentas.
- B7: al cambiar la versión vigente, quien aceptó la anterior vuelve a B6.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from main import app
from src.config.dependencies import get_google_oauth_service
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from src.modules.user.domain.services import terms_of_service
from tests.conftest import (
    _URL_DE_LA_BD_DE_TEST,
    create_authenticated_user,
    set_auth_cookies,
)

pytestmark = pytest.mark.asyncio

PASSWORD = "V@l1dP@ss123!"
ACCEPT = "/api/v1/users/me/accept-terms"
CURRENT_USER = "/api/v1/auth/current-user"
PROTEGIDA = "/api/v1/users/me/stats"


async def _sql(sql: str, params: dict | None = None):
    engine = create_async_engine(_URL_DE_LA_BD_DE_TEST["url"])
    try:
        async with engine.begin() as conn:
            resultado = await conn.execute(text(sql), params or {})
            return resultado.all() if resultado.returns_rows else []
    finally:
        await engine.dispose()


async def _terminos_en_bd(email: str) -> tuple | None:
    filas = await _sql(
        "SELECT terms_accepted_at, terms_version FROM users WHERE email = :email",
        {"email": email},
    )
    return tuple(filas[0]) if filas else None


async def _sin_aceptar(client: AsyncClient, email: str | None = None) -> tuple[str, dict]:
    """Un usuario con sesión y SIN los Términos aceptados (como los de antes de la migración)."""
    email = email or f"sin-terminos-{uuid.uuid4().hex[:8]}@example.com"
    datos = await create_authenticated_user(client, email, PASSWORD, "Sin", "Terminos")
    await _sql(
        "UPDATE users SET terms_accepted_at = NULL, terms_version = NULL WHERE email = :email",
        {"email": email},
    )
    set_auth_cookies(client, datos["cookies"])
    return email, datos


def _registro(email: str, **extra) -> dict:
    return {
        "email": email,
        "password": PASSWORD,
        "first_name": "Ana",
        "last_name": "Lopez",
        "gender": "FEMALE",
        **extra,
    }


class TestRegistro:
    async def test_register_with_accept_terms_stores_version_and_date(self, client: AsyncClient):
        """
        Given: Un registro con accept_terms true (B1)
        When: Se envía
        Then: 201, la respuesta dice que aceptó, y en BD están la versión vigente y la fecha
        """
        respuesta = await client.post(
            "/api/v1/auth/register", json=_registro("b1@example.com", accept_terms=True)
        )

        assert respuesta.status_code == 201
        assert respuesta.json()["terms_accepted"] is True
        aceptado_en, version = await _terminos_en_bd("b1@example.com")
        assert version == terms_of_service.current_terms_version()
        assert aceptado_en is not None
        assert aceptado_en.tzinfo is not None

    @pytest.mark.parametrize("extra", [{}, {"accept_terms": False}, {"accept_terms": None}])
    async def test_register_without_accept_terms_is_422_and_creates_nothing(
        self, client: AsyncClient, extra
    ):
        """
        Given: Un registro sin accept_terms, o con false o null (B2)
        When: Se envía
        Then: 422 y no se crea ningún usuario
        """
        respuesta = await client.post(
            "/api/v1/auth/register", json=_registro("b2@example.com", **extra)
        )

        assert respuesta.status_code == 422
        assert await _terminos_en_bd("b2@example.com") is None


class TestAltaConGoogle:
    async def test_google_new_user_has_no_acceptance_and_is_blocked(self, client: AsyncClient):
        """
        Given: Alguien que entra por primera vez con Google (B3)
        When: Se le da de alta y llama a una ruta con sesión
        Then: En BD sin aceptación, la respuesta lo dice, y la ruta da 403 TERMS_NOT_ACCEPTED
        """
        google = AsyncMock()
        google.exchange_code_for_user_info.return_value = GoogleUserInfo(
            google_user_id="google-b3",
            email="b3@gmail.com",
            first_name="Nuevo",
            last_name="Google",
            email_verified=True,
            picture_url=None,
        )
        app.dependency_overrides[get_google_oauth_service] = lambda: google

        respuesta = await client.post("/api/v1/auth/google", json={"authorization_code": "code"})

        assert respuesta.status_code == 200
        assert respuesta.json()["user"]["terms_accepted"] is False
        assert await _terminos_en_bd("b3@gmail.com") == (None, None)
        set_auth_cookies(client, dict(respuesta.cookies))
        bloqueada = await client.get(PROTEGIDA)
        assert bloqueada.status_code == 403
        assert bloqueada.json()["error_code"] == "TERMS_NOT_ACCEPTED"


class TestUsuarioActual:
    async def test_current_user_and_login_report_terms(self, client: AsyncClient):
        """
        Given: Un usuario que aceptó al registrarse (B4)
        When: Pide current-user y hace login
        Then: Los dos traen terms_accepted true y la versión exigida
        """
        datos = await create_authenticated_user(client, "b4@example.com", PASSWORD, "Ana", "Lopez")
        set_auth_cookies(client, datos["cookies"])

        actual = (await client.get(CURRENT_USER)).json()

        vigente = terms_of_service.current_terms_version()
        assert actual["terms_accepted"] is True
        assert actual["terms_version_required"] == vigente
        assert datos["user"]["terms_accepted"] is True
        assert datos["user"]["terms_version_required"] == vigente


class TestGuarda:
    async def test_protected_routes_answer_403_terms_not_accepted(self, client: AsyncClient):
        """
        Given: Un usuario con sesión sin los Términos aceptados (B6, B8)
        When: Lee y escribe en rutas con sesión no exentas
        Then: 403 con detail y error_code TERMS_NOT_ACCEPTED
        """
        await _sin_aceptar(client)

        lectura = await client.get(PROTEGIDA)
        escritura = await client.patch("/api/v1/users/profile", json={"first_name": "Otro"})
        competicion = await client.get("/api/v1/competitions")

        for respuesta in (lectura, escritura, competicion):
            assert respuesta.status_code == 403
            cuerpo = respuesta.json()
            assert cuerpo["error_code"] == "TERMS_NOT_ACCEPTED"
            assert cuerpo["detail"]

    async def test_exempt_routes_work_without_acceptance(self, client: AsyncClient):
        """
        Given: Un usuario con sesión sin los Términos aceptados (B6)
        When: Pide current-user, refresca la sesión y cierra sesión
        Then: Todo responde 200; current-user dice que no ha aceptado
        """
        _, datos = await _sin_aceptar(client)

        actual = await client.get(CURRENT_USER)
        refresco = await client.post("/api/v1/auth/refresh-token")
        set_auth_cookies(client, datos["cookies"])
        salida = await client.post("/api/v1/auth/logout", json={})

        assert actual.status_code == 200
        assert actual.json()["terms_accepted"] is False
        assert actual.json()["terms_version_required"] == terms_of_service.current_terms_version()
        assert refresco.status_code == 200
        assert refresco.json()["user"]["terms_accepted"] is False
        assert salida.status_code == 200

    async def test_public_routes_are_not_affected(self, client: AsyncClient):
        """
        Given: Un usuario con sesión sin los Términos aceptados, y otro sin sesión
        When: Piden una ruta pública
        Then: 200 los dos
        """
        await _sin_aceptar(client)
        con_sesion = await client.get("/api/v1/countries")
        client.cookies.clear()
        sin_sesion = await client.get("/api/v1/countries")

        assert con_sesion.status_code == 200
        assert sin_sesion.status_code == 200

    async def test_no_session_is_still_401(self, client: AsyncClient):
        """
        Given: Nadie con sesión
        When: Pide una ruta con sesión
        Then: 401, no 403: la guarda va después de autenticar
        """
        respuesta = await client.get(PROTEGIDA)

        assert respuesta.status_code == 401


class TestAceptar:
    async def test_accept_terms_unblocks_the_user(self, client: AsyncClient):
        """
        Given: Un usuario sin los Términos aceptados (B5)
        When: Acepta
        Then: 200 con terms_accepted true, en BD la versión vigente y la fecha, y ya puede usar la app
        """
        email, _ = await _sin_aceptar(client)

        respuesta = await client.post(ACCEPT)

        assert respuesta.status_code == 200
        assert respuesta.json()["terms_accepted"] is True
        assert respuesta.json()["email"] == email
        aceptado_en, version = await _terminos_en_bd(email)
        assert version == terms_of_service.current_terms_version()
        assert aceptado_en is not None
        assert (await client.get(PROTEGIDA)).status_code == 200

    async def test_accept_terms_twice_keeps_the_first_date(self, client: AsyncClient):
        """
        Given: Un usuario que ya aceptó la vigente (B5)
        When: Vuelve a aceptar
        Then: 200 y la fecha en BD no cambia
        """
        email, _ = await _sin_aceptar(client)
        await client.post(ACCEPT)
        primera = await _terminos_en_bd(email)

        otra_vez = await client.post(ACCEPT)

        assert otra_vez.status_code == 200
        assert await _terminos_en_bd(email) == primera

    async def test_accept_terms_requires_session(self, client: AsyncClient):
        """
        Given: Nadie con sesión
        When: Intenta aceptar
        Then: 401
        """
        assert (await client.post(ACCEPT)).status_code == 401


class TestCambioDeVersion:
    async def test_new_version_blocks_until_accepted_again(self, client: AsyncClient, monkeypatch):
        """
        Given: Un usuario que aceptó la versión vigente (B7)
        When: El backend pasa a otra versión
        Then: 403 TERMS_NOT_ACCEPTED hasta que acepta la nueva, que queda en BD
        """
        email = "b7@example.com"
        datos = await create_authenticated_user(client, email, PASSWORD, "Ana", "Lopez")
        set_auth_cookies(client, datos["cookies"])
        assert (await client.get(PROTEGIDA)).status_code == 200

        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", "2099-01-01")

        bloqueada = await client.get(PROTEGIDA)
        assert bloqueada.status_code == 403
        assert bloqueada.json()["error_code"] == "TERMS_NOT_ACCEPTED"
        assert (await client.get(CURRENT_USER)).json()["terms_version_required"] == "2099-01-01"

        assert (await client.post(ACCEPT)).status_code == 200
        assert (await client.get(PROTEGIDA)).status_code == 200
        assert (await _terminos_en_bd(email))[1] == "2099-01-01"
