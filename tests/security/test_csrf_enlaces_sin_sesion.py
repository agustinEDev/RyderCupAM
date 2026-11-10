"""
Las rutas de los enlaces del correo se usan sin sesión (fase 3, H-1): con el CSRF
encendido y sin cookie, `POST /auth/validate-reset-token` y `POST
/auth/resend-verification-link` (pedir otro enlace con el caducado) responden; la
primera daba 403. `/auth/resend-verification` (por correo) pide sesión y CSRF. Son públicas, con su límite, y
responden lo mismo exista o no la cuenta: un sitio ajeno no consigue nada que no pueda
pedir directamente.
"""

import os
import uuid

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def con_csrf():
    """El CSRF encendido, como en producción."""
    antes = os.environ.get("TEST_CSRF")
    os.environ["TEST_CSRF"] = "true"
    yield
    if antes is None:
        os.environ.pop("TEST_CSRF", None)
    else:
        os.environ["TEST_CSRF"] = antes


@pytest.mark.asyncio
async def test_h1_validating_a_reset_link_works_without_a_session(client: AsyncClient):
    """
    Given: Un navegador sin sesión ni cookie CSRF
    When: Valida un enlace de restablecer por POST
    Then: 200 (valid=False con un token que no es), no 403
    """
    client.cookies.clear()

    r = await client.post("/api/v1/auth/validate-reset-token", json={"token": "x" * 43})

    assert r.status_code == status.HTTP_200_OK, r.text
    assert r.json()["valid"] is False


@pytest.mark.asyncio
async def test_h1_resending_from_an_expired_link_works_without_a_session(client: AsyncClient):
    """
    Given: Un navegador sin sesión ni cookie CSRF (la pantalla de «enlace caducado»)
    When: Pide otro enlace presentando el caducado
    Then: 200 con el mensaje genérico, no 403
    """
    client.cookies.clear()

    r = await client.post(
        "/api/v1/auth/resend-verification-link",
        json={"token": f"token-{uuid.uuid4().hex}"},
    )

    assert r.status_code == status.HTTP_200_OK, r.text


@pytest.mark.asyncio
async def test_h1_other_routes_still_need_the_token(client: AsyncClient):
    """
    Given: Un navegador sin cookie CSRF
    When: Llama a una ruta que no es pública (desbloquear una cuenta, de admin)
    Then: 403 CSRF_VALIDATION_FAILED: el cambio solo exime las dos rutas
    """
    client.cookies.clear()

    r = await client.post("/api/v1/auth/unlock-account", json={"user_id": str(uuid.uuid4())})

    assert r.status_code == status.HTTP_403_FORBIDDEN
    assert r.json()["error_code"] == "CSRF_VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_h1_resending_by_email_is_no_longer_exempt(client: AsyncClient):
    """
    Given: Un navegador sin sesión ni cookie CSRF
    When: Pide reenviar por correo (la forma con sesión, la del aviso de la app)
    Then: 403 CSRF_VALIDATION_FAILED: ya no es pública
    """
    client.cookies.clear()

    r = await client.post("/api/v1/auth/resend-verification", json={"email": "nadie@example.com"})

    assert r.status_code == status.HTTP_403_FORBIDDEN
    assert r.json()["error_code"] == "CSRF_VALIDATION_FAILED"
