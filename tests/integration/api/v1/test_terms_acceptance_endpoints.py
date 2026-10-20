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


def _google(email: str, google_id: str = "google-existente"):
    google = AsyncMock()
    google.exchange_code_for_user_info.return_value = GoogleUserInfo(
        google_user_id=google_id,
        email=email,
        first_name="Ana",
        last_name="Lopez",
        email_verified=True,
        picture_url=None,
    )
    app.dependency_overrides[get_google_oauth_service] = lambda: google
    return google


class TestGoogleConUsuarioExistente:
    async def test_google_login_of_an_existing_user_keeps_its_acceptance(self, client: AsyncClient):
        """
        Given: Un usuario que aceptó los Términos al registrarse
        When: Entra con Google con el mismo email (se vincula solo) y vuelve a
            entrar con la cuenta de Google ya vinculada
        Then: Su aceptación en BD no cambia, y la respuesta dice que aceptó
        """
        email = "existente@example.com"
        await create_authenticated_user(client, email, PASSWORD, "Ana", "Lopez")
        antes = await _terminos_en_bd(email)
        assert antes[1] == terms_of_service.current_terms_version()
        _google(email)

        vincula = await client.post("/api/v1/auth/google", json={"authorization_code": "c1"})
        client.cookies.clear()
        vinculada = await client.post("/api/v1/auth/google", json={"authorization_code": "c2"})

        assert vincula.status_code == 200
        assert vincula.json()["is_new_user"] is False
        assert vincula.json()["user"]["terms_accepted"] is True
        assert vinculada.status_code == 200
        assert vinculada.json()["user"]["terms_accepted"] is True
        assert await _terminos_en_bd(email) == antes

    async def test_linking_google_from_the_profile_keeps_the_acceptance(self, client: AsyncClient):
        """
        Given: Un usuario que aceptó los Términos, con sesión
        When: Vincula Google desde su perfil
        Then: 200 y su aceptación en BD no cambia
        """
        email = "vincula@example.com"
        datos = await create_authenticated_user(client, email, PASSWORD, "Ana", "Lopez")
        antes = await _terminos_en_bd(email)
        set_auth_cookies(client, datos["cookies"])
        _google(email, google_id="google-perfil")

        respuesta = await client.post(
            "/api/v1/auth/google/link", json={"authorization_code": "code"}
        )

        assert respuesta.status_code == 200
        assert await _terminos_en_bd(email) == antes


async def _historial(email: str) -> list[tuple]:
    """Las filas de terms_acceptances de ese usuario, de la más antigua a la más reciente."""
    return await _sql(
        "SELECT a.terms_version, a.accepted_at, a.ip_address, a.user_agent "
        "FROM terms_acceptances a JOIN users u ON u.id = a.user_id "
        "WHERE u.email = :email ORDER BY a.accepted_at",
        {"email": email},
    )


class TestHistorial:
    async def test_register_records_one_acceptance_with_the_request_identity(
        self, authenticated_client
    ):
        """
        Given: Un registro con accept_terms true desde un navegador (fixture authenticated_client)
        When: Se mira el historial
        Then: Una fila con la versión vigente, la misma fecha que el usuario, el
            navegador de la petición y la IP que la API saca de la petición (la
            misma que guarda para el dispositivo del login)
        """
        client, datos = authenticated_client
        email = datos["credentials"]["email"]

        filas = await _historial(email)
        dispositivos = (await client.get("/api/v1/users/me/devices")).json()["devices"]

        assert len(filas) == 1
        version, aceptado_en, ip, navegador = filas[0]
        assert version == terms_of_service.current_terms_version()
        assert aceptado_en == (await _terminos_en_bd(email))[0]
        assert navegador == client.headers["User-Agent"]
        assert ip is not None
        assert ip == dispositivos[0]["ip_address"]

    async def test_accepting_the_same_version_adds_no_row(self, client: AsyncClient):
        """
        Given: Un usuario que aceptó al registrarse
        When: Vuelve a aceptar la misma versión
        Then: 200 y el historial sigue con una sola fila
        """
        email = "mismo@example.com"
        datos = await create_authenticated_user(client, email, PASSWORD, "Ana", "Lopez")
        set_auth_cookies(client, datos["cookies"])

        respuesta = await client.post(ACCEPT)

        assert respuesta.status_code == 200
        assert len(await _historial(email)) == 1

    async def test_new_version_adds_a_row_and_keeps_the_old_one(
        self, client: AsyncClient, monkeypatch
    ):
        """
        Given: Un usuario que aceptó la versión vigente al registrarse
        When: Cambia la versión y acepta la nueva
        Then: Dos filas: la anterior intacta y la nueva
        """
        email = "historial@example.com"
        datos = await create_authenticated_user(client, email, PASSWORD, "Ana", "Lopez")
        set_auth_cookies(client, datos["cookies"])
        anterior = await _historial(email)
        monkeypatch.setattr(terms_of_service, "CURRENT_TERMS_VERSION", "2099-01-01")

        assert (await client.post(ACCEPT)).status_code == 200

        filas = await _historial(email)
        assert len(filas) == 2
        assert filas[0] == anterior[0]
        assert filas[1][0] == "2099-01-01"
        assert filas[1][1] == (await _terminos_en_bd(email))[0]

    async def test_accept_terms_records_the_request_identity(self, authenticated_client):
        """
        Given: Un usuario con sesión y los Términos pendientes
        When: Acepta desde su navegador
        Then: La fila nueva lleva el navegador de la petición y la IP que la API
            saca de ella (la misma que la de su dispositivo)
        """
        client, datos = authenticated_client
        email = datos["credentials"]["email"]
        await _sql(
            "UPDATE users SET terms_accepted_at = NULL, terms_version = NULL WHERE email = :email",
            {"email": email},
        )
        dispositivos = (await client.get("/api/v1/users/me/devices")).json()["devices"]

        assert (await client.post(ACCEPT)).status_code == 200

        filas = await _historial(email)
        assert len(filas) == 2
        _, _, ip, navegador = filas[1]
        assert navegador == client.headers["User-Agent"]
        assert ip is not None
        assert ip == dispositivos[0]["ip_address"]


class TestDispositivosSinAceptar:
    async def test_devices_can_be_listed_and_revoked_with_terms_pending(self, authenticated_client):
        """
        Given: Un usuario con sesión y los Términos pendientes
        When: Lista sus dispositivos y revoca uno
        Then: 200 las dos (cerrar una sesión robada no espera a aceptar), y el
            resto de /users/me/... sigue bloqueado con 403 TERMS_NOT_ACCEPTED
        """
        client, datos = authenticated_client
        await _sql(
            "UPDATE users SET terms_accepted_at = NULL, terms_version = NULL WHERE email = :email",
            {"email": datos["credentials"]["email"]},
        )

        bloqueadas = [
            await client.get("/api/v1/users/me/stats"),
            await client.get("/api/v1/users/me/avatar/uploads"),
            await client.delete("/api/v1/users/me/avatar"),
            await client.get("/api/v1/users/me/matches"),
        ]
        lista = await client.get("/api/v1/users/me/devices")
        dispositivo = lista.json()["devices"][0]["id"]
        revocar = await client.delete(f"/api/v1/users/me/devices/{dispositivo}")

        for respuesta in bloqueadas:
            assert respuesta.status_code == 403
            assert respuesta.json()["error_code"] == "TERMS_NOT_ACCEPTED"
        assert lista.status_code == 200
        assert revocar.status_code == 200
