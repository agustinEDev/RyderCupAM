"""
Vincular Google desde el perfil queda en el log de seguridad, con la red, y un log
roto no cambia la respuesta (revisión del registro con Google, BE #744).
"""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.config.dependencies import get_google_oauth_service
from src.modules.user.application.ports.google_oauth_service_interface import GoogleUserInfo
from src.shared.infrastructure.logging.security_logger import SecurityLogger
from tests.conftest import create_authenticated_user, set_auth_cookies

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"


def _google(email: str) -> None:
    google = AsyncMock()
    google.exchange_code_for_user_info.return_value = GoogleUserInfo(
        google_user_id=f"google-{email}",
        email=email,
        first_name="Ana",
        last_name="Lopez",
        email_verified=True,
        picture_url=None,
    )
    app.dependency_overrides[get_google_oauth_service] = lambda: google


async def _verifica(email: str) -> None:
    from tests.integration.api.v1.test_sesion_desactivada_y_codigos import _sql

    await _sql("update users set email_verified = true where email = :e", e=email)


async def _vincula(client: AsyncClient, email: str, verificada: bool = True):
    datos = await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    if verificada:
        # Vincular Google pide el correo verificado (#749)
        await _verifica(email)
    set_auth_cookies(client, datos["cookies"])
    _google(email)
    respuesta = await client.post(
        "/api/v1/auth/google/link",
        json={"authorization_code": "code"},
        headers={"User-Agent": "Navegador de prueba", "X-Forwarded-For": "203.0.113.100"},
    )
    return datos, respuesta


async def test_linking_google_from_the_profile_is_logged_with_the_network(
    client: AsyncClient, monkeypatch
):
    """
    Given: Un usuario con sesión
    When: Vincula Google desde su perfil
    Then: 200, y el log apunta un vínculo manual con su navegador y una IP
    """
    apuntes = []
    monkeypatch.setattr(
        SecurityLogger, "log_google_account_linked", lambda self, **kw: apuntes.append(kw)
    )

    datos, respuesta = await _vincula(client, "vinculo.log@example.com")

    assert respuesta.status_code == 200
    assert len(apuntes) == 1
    assert apuntes[0]["user_id"] == datos["user"]["id"]
    assert apuntes[0]["automatic"] is False
    assert apuntes[0]["user_agent"] == "Navegador de prueba"
    assert apuntes[0]["ip_address"] == "203.0.113.100"


async def test_a_broken_log_does_not_change_the_link_answer(client: AsyncClient, monkeypatch):
    """
    Given: El log de seguridad falla
    When: Vincula Google desde su perfil
    Then: 200 igual: el vínculo ya está guardado y el log nunca cambia la respuesta
    """

    def roto(self, **kw):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(SecurityLogger, "log_google_account_linked", roto)

    _datos, respuesta = await _vincula(client, "vinculo.roto@example.com")

    assert respuesta.status_code == 200


async def test_a_deactivated_account_gets_its_own_code_on_google(client: AsyncClient):
    """
    Given: Una cuenta vinculada a Google y desactivada por un administrador
    When: Entra con Google
    Then: 403 con error_code ACCOUNT_DEACTIVATED, para que la app diga que está
          desactivada en vez de invitar a reintentar
    """
    from tests.integration.api.v1.test_sesion_desactivada_y_codigos import _sql

    email = "desactivada.google@example.com"
    await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    _google(email)
    primera = await client.post("/api/v1/auth/google", json={"authorization_code": "c1"})
    assert primera.status_code == 200
    await _sql("update users set is_active = false where email = :e", e=email)
    client.cookies.clear()

    respuesta = await client.post("/api/v1/auth/google", json={"authorization_code": "c2"})

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCOUNT_DEACTIVATED"
    assert respuesta.json()["detail"] == (
        "This account has been deactivated. Contact an administrator."
    )


async def test_g2_google_takes_an_unverified_account_from_whoever_had_it(client: AsyncClient):
    """
    Given: Una cuenta creada con contraseña y sin verificar, con su sesión abierta
           (la pudo crear cualquiera con ese correo)
    When: Entra un Google que verificó ese correo
    Then: La sesión de antes queda fuera al momento (acceso y refresco, 401) y la
          contraseña ya no entra; la sesión de Google sí
    """
    email = "precaptura@example.com"
    otro = await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    assert otro["user"]["email_verified"] is False
    _google(email)
    google = await client.post("/api/v1/auth/google", json={"authorization_code": "c1"})
    assert google.status_code == 200
    de_google = dict(google.cookies)
    client.cookies.clear()

    set_auth_cookies(client, otro["cookies"])
    acceso = await client.get("/api/v1/auth/current-user")
    refresco = await client.post("/api/v1/auth/refresh-token")
    client.cookies.clear()
    contrasena = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE},
        headers={"X-Test-Client-ID": "precaptura-login"},
    )
    set_auth_cookies(client, de_google)
    suya = await client.get("/api/v1/auth/current-user")

    assert acceso.status_code == 401
    assert refresco.status_code == 401
    assert contrasena.status_code == 401
    assert suya.status_code == 200
    assert suya.json()["email_verified"] is True


async def test_linking_google_needs_a_verified_email(client: AsyncClient):
    """
    Given: Un usuario con sesión y el correo SIN verificar
    When: Vincula Google desde su perfil
    Then: 403 con GOOGLE_LINK_NEEDS_VERIFIED_EMAIL y sin vínculo
    """
    _datos, respuesta = await _vincula(client, "sin.verificar.link@example.com", verificada=False)

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "GOOGLE_LINK_NEEDS_VERIFIED_EMAIL"


async def test_g1_the_creator_google_link_does_not_survive_the_claim(client: AsyncClient):
    """
    Given: Una cuenta sin verificar a la que su creador vinculó SU Google (antes de
           la regla de hoy, o con la cuenta verificada y luego otro correo)
    When: Entra el Google que verificó el correo de la cuenta
    Then: 200 contra la restricción real de la BD (un Google por cuenta), el Google
          del creador ya no da esa cuenta y el del dueño sí
    """
    from tests.integration.api.v1.test_terms_acceptance_endpoints import _sql

    email = "precaptura.google@example.com"
    await create_authenticated_user(client, email, CLAVE, "Ana", "Lopez")
    await _sql(
        "insert into user_oauth_accounts (id, user_id, provider, provider_user_id, "
        "provider_email, created_at) select gen_random_uuid()::text, id, 'google', "
        "'google-del-creador', 'creador@example.com', now() from users where email = :e",
        {"e": email},
    )
    _google(email)

    duenno = await client.post("/api/v1/auth/google", json={"authorization_code": "c1"})

    assert duenno.status_code == 200
    vinculos = await _sql(
        "select o.provider_user_id from user_oauth_accounts o join users u "
        "on u.id = o.user_id where u.email = :e",
        {"e": email},
    )
    assert [fila[0] for fila in vinculos] == [f"google-{email}"]


async def test_r1_resetting_after_an_email_change_takes_the_creator_google_away(
    client: AsyncClient,
):
    """
    Given: Una cuenta verificada con SU Google, a la que su dueño le cambió el correo por
           el de otra persona (queda sin verificar y con ese Google)
    When: La otra persona usa «Olvidé mi contraseña» con el enlace de su buzón
    Then: La cuenta queda verificada y sin aquel Google: ya no entra con él
    """
    from tests.conftest import get_user_by_email
    from tests.integration.api.v1.test_terms_acceptance_endpoints import _sql

    antes, despues = "creador.cambio@example.com", "victima.cambio@example.com"
    await create_authenticated_user(client, antes, CLAVE, "Ana", "Lopez")
    await _sql(
        "insert into user_oauth_accounts (id, user_id, provider, provider_user_id, "
        "provider_email, created_at) select gen_random_uuid()::text, id, 'google', "
        "'google-del-creador', 'creador@example.com', now() from users where email = :e",
        {"e": antes},
    )
    await _sql(
        "update users set email = :d, email_verified = false where email = :a",
        {"a": antes, "d": despues},
    )
    client.cookies.clear()
    await client.post("/api/v1/auth/forgot-password", json={"email": despues})
    token = (await get_user_by_email(client, despues)).password_reset_token

    r = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "OtraClave#2026segura"}
    )

    assert r.status_code == 200
    filas = await _sql(
        "select u.email_verified, (select count(*) from user_oauth_accounts o "
        "where o.user_id = u.id) from users u where u.email = :e",
        {"e": despues},
    )
    assert filas == [(True, 0)]
