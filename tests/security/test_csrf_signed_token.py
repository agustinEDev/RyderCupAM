"""
El middleware exige que el token CSRF sea del usuario de la sesión (BE #724).

Además de cabecera == cookie, con sesión el token tiene que llevar la firma de
ESE usuario: una cookie plantada desde otro subdominio ya no basta, porque quien
la planta no sabe firmar para la víctima. El usuario sale del JWT de la cookie de
acceso (aunque haya caducado: la firma del JWT sí se comprueba), o del de la de
refresh, o del Bearer. Sin sesión no hay nada que suplantar y se queda el
double-submit de siempre.

  #  sesión                       | token (cabecera = cookie)  | resultado
  ---|----------------------------|----------------------------|--------------------------
  21 A                            | el de A                    | pasa
  22 A                            | sin firmar (formato viejo) | 403 CSRF
  23 A                            | el de B                    | 403 CSRF
  24 A con el acceso CADUCADO     | el de B                    | 403 CSRF: su `sub` cuenta
  25 A solo con la de refresh     | el de B / el de A          | 403 CSRF / pasa la CSRF
  26 ninguna                      | cualquiera                 | pasa la CSRF (luego 401)
  27 A, en `/auth/google/link`    | ninguno                    | 403 CSRF: ya no está exenta
  28 A tras renovar               | el que trae la renovación  | pasa
  29 A por Bearer, sin cookies    | el de B / el de A          | 403 CSRF / pasa
  30 A con un JWT de acceso falso | el de B                    | no cuenta: si la de refresh
                                                                  es de A, 403 CSRF
  31 A / ninguna                  | con caracteres no ASCII    | 403 CSRF, no un 500 (revisor)
  32 acceso de B + refresh de A   | el de B                    | 403 CSRF: una cookie de acceso
                                                                  plantada no suplanta la sesión
                                                                  (code-review)
"""

import os
import secrets
import time

import jwt
import pytest
from fastapi import status
from httpx import AsyncClient

from src.config.csrf_config import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from src.config.settings import settings

pytestmark = pytest.mark.asyncio

PASS = "SecurePassword123!"


@pytest.fixture(scope="module", autouse=True)
def con_csrf():
    """La validación CSRF encendida para este módulo (como `test_csrf_protection`)."""
    antes = os.environ.get("TEST_CSRF")
    os.environ["TEST_CSRF"] = "true"
    yield
    if antes is None:
        os.environ.pop("TEST_CSRF", None)
    else:
        os.environ["TEST_CSRF"] = antes


async def _entra(client: AsyncClient, email: str) -> dict:
    """Registra (si hace falta) y entra: devuelve el cuerpo del login."""
    alta = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASS,
            "first_name": "Csrf",
            "last_name": "Firma",
            "accept_terms": True,
        },
    )
    # Con el correo ya registrado también es 201: el registro no lo dice (fase 3)
    assert alta.status_code == status.HTTP_201_CREATED, alta.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASS})
    assert login.status_code == status.HTTP_200_OK, login.text
    return login.json()


@pytest.fixture
async def dos(client: AsyncClient):
    """B entra primero (para tener su token) y después A: la sesión que queda es la de A."""
    b = await _entra(client, "csrf_b@example.com")
    a = await _entra(client, "csrf_a@example.com")
    return client, a, b


async def _toca_el_perfil(client: AsyncClient, token: str | None, **extra):
    """Ayudante del test: toca el perfil."""
    if token is not None:
        client.cookies.set(CSRF_COOKIE_NAME, token)
    cabeceras = {CSRF_HEADER_NAME: token} if token is not None else {}
    cabeceras.update(extra.pop("headers", {}))
    return await client.patch(
        "/api/v1/users/profile", json={"first_name": "Ana"}, headers=cabeceras
    )


def _es_rechazo_csrf(respuesta) -> bool:
    """Ayudante del test: es rechazo csrf."""
    return (
        respuesta.status_code == status.HTTP_403_FORBIDDEN
        and respuesta.json().get("error_code") == "CSRF_VALIDATION_FAILED"
    )


async def test_csrf_token_of_a_for_session_of_a_is_accepted(dos):
    """
    Given: La sesión de A y un token CSRF emitido para A
    When: A hace una petición que cambia estado
    Then: Pasa el CSRF
    """
    client, a, _ = dos

    respuesta = await _toca_el_perfil(client, a["csrf_token"])

    assert respuesta.status_code == status.HTTP_200_OK, respuesta.text


async def test_csrf_unsigned_token_is_rejected(dos):
    """
    Given: La sesión de A y un token sin firmar igual en cabecera y cookie
    When: A hace una petición que cambia estado
    Then: 403 CSRF_VALIDATION_FAILED
    """
    client, _, _ = dos

    assert _es_rechazo_csrf(await _toca_el_perfil(client, secrets.token_urlsafe(32)))


async def test_csrf_token_of_b_for_session_of_a_is_rejected(dos):
    """
    Given: La sesión de A con el token CSRF de B en cabecera y cookie
    When: A hace una petición que cambia estado
    Then: 403
    """
    client, _, b = dos

    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"]))


async def test_csrf_expired_access_token_still_binds_its_user(dos):
    """
    Given: El access JWT de A caducado y sin cookie de refresh
    When: Llega con el token CSRF de B
    Then: 403: el usuario del JWT caducado sigue contando
    """
    client, a, b = dos
    # A mano y en UTC: `create_access_token` calcula `exp` con la hora local sin
    # zona, y con UTC+1 «hace 5 minutos» caducaría dentro de 55
    caducado = jwt.encode(
        {"sub": a["user"]["id"], "type": "access", "exp": int(time.time()) - 600},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    client.cookies.set("access_token", caducado)
    # Sin la de refresh: solo el acceso caducado dice de quién es la sesión
    client.cookies.delete("refresh_token")

    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"]))


async def test_csrf_only_refresh_cookie_binds_its_user(dos):
    """
    Given: Solo la cookie de refresh de A
    When: Llega con el token de B y luego con el de A
    Then: El de B da 403 y el de A pasa
    """
    client, a, b = dos
    client.cookies.delete("access_token")

    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"]))
    assert not _es_rechazo_csrf(await _toca_el_perfil(client, a["csrf_token"]))


async def test_csrf_without_session_keeps_plain_double_submit(client: AsyncClient):
    """
    Given: Ninguna sesión
    When: Llega un token cualquiera igual en cabecera y cookie
    Then: Pasa el CSRF y la petición acaba en 401
    """
    client.cookies.clear()

    respuesta = await _toca_el_perfil(client, secrets.token_urlsafe(32))

    assert not _es_rechazo_csrf(respuesta)
    assert respuesta.status_code == status.HTTP_401_UNAUTHORIZED


async def test_csrf_google_link_is_no_longer_exempt(dos):
    """
    Given: La sesión de A
    When: Llama a POST /auth/google/link sin token CSRF
    Then: 403: ya no está exenta por prefijo
    """
    client, _, _ = dos

    respuesta = await client.post(
        "/api/v1/auth/google/link", json={"code": "x", "redirect_uri": "http://x"}
    )

    assert _es_rechazo_csrf(respuesta)


async def test_csrf_after_refresh_new_token_is_accepted(dos):
    """
    Given: La sesión de A
    When: Renueva con /auth/refresh-token
    Then: El token CSRF nuevo está firmado para A y pasa
    """
    client, a, _ = dos
    renovada = await client.post("/api/v1/auth/refresh-token")
    assert renovada.status_code == status.HTTP_200_OK, renovada.text
    nuevo = renovada.json()["csrf_token"]

    assert nuevo != a["csrf_token"]
    respuesta = await _toca_el_perfil(client, nuevo)
    assert respuesta.status_code == status.HTTP_200_OK, respuesta.text


async def test_csrf_bearer_token_binds_its_user(dos):
    """
    Given: Solo un Bearer de A, sin cookies de sesión
    When: Llega con el token de B y luego con el de A
    Then: El de B da 403 y el de A pasa
    """
    client, a, b = dos
    client.cookies.delete("access_token")
    client.cookies.delete("refresh_token")
    bearer = {"Authorization": f"Bearer {a['access_token']}"}

    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"], headers=bearer))
    respuesta = await _toca_el_perfil(client, a["csrf_token"], headers=bearer)
    assert respuesta.status_code == status.HTTP_200_OK, respuesta.text


async def test_csrf_forged_access_jwt_is_ignored_and_refresh_user_counts(dos):
    """
    Given: Un access JWT de B firmado con otra clave junto al refresh de A
    When: Llega con el token de B
    Then: 403: el JWT falso no cuenta y manda el refresh de A
    """
    client, _, b = dos
    falso = jwt.encode(
        {"sub": b["user"]["id"], "type": "access"}, "no-es-la-clave", algorithm=settings.ALGORITHM
    )
    client.cookies.set("access_token", falso)

    # El falso dice B, pero no se cree: manda la de refresh, que es de A
    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"]))


@pytest.mark.parametrize("con_sesion", [True, False])
async def test_csrf_non_ascii_header_returns_403(client: AsyncClient, con_sesion):
    """
    Given: Con sesión o sin ella
    When: Llega un X-CSRF-Token con bytes no ASCII
    Then: 403, nunca 500
    """
    if con_sesion:
        await _entra(client, "csrf_a@example.com")
    else:
        client.cookies.clear()
    client.cookies.set(CSRF_COOKIE_NAME, "abc")

    respuesta = await client.patch(
        "/api/v1/users/profile",
        json={"first_name": "Ana"},
        # En bytes: httpx no deja mandar texto no ASCII, el navegador sí
        headers={CSRF_HEADER_NAME: "ñandú.ñ".encode()},
    )

    assert _es_rechazo_csrf(respuesta)


async def test_csrf_access_of_other_user_with_own_refresh_is_rejected(dos):
    """
    Given: El access JWT de B junto al refresh de A
    When: Llega con el token de B
    Then: 403: el token tiene que valer para todos los usuarios de la sesión
    """
    client, _, b = dos
    # La sesión es de A (su refresh); alguien planta el acceso de B y el token de B
    client.cookies.set("access_token", b["access_token"])

    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"]))
