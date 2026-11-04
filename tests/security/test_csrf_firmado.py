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
    assert alta.status_code in (status.HTTP_201_CREATED, status.HTTP_409_CONFLICT), alta.text
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
    if token is not None:
        client.cookies.set(CSRF_COOKIE_NAME, token)
    cabeceras = {CSRF_HEADER_NAME: token} if token is not None else {}
    cabeceras.update(extra.pop("headers", {}))
    return await client.patch(
        "/api/v1/users/profile", json={"first_name": "Ana"}, headers=cabeceras
    )


def _es_rechazo_csrf(respuesta) -> bool:
    return (
        respuesta.status_code == status.HTTP_403_FORBIDDEN
        and respuesta.json().get("error_code") == "CSRF_VALIDATION_FAILED"
    )


async def test_21_el_token_de_a_vale_para_a(dos):
    client, a, _ = dos

    respuesta = await _toca_el_perfil(client, a["csrf_token"])

    assert respuesta.status_code == status.HTTP_200_OK, respuesta.text


async def test_22_un_token_sin_firmar_ya_no_vale(dos):
    client, _, _ = dos

    assert _es_rechazo_csrf(await _toca_el_perfil(client, secrets.token_urlsafe(32)))


async def test_23_el_token_de_b_no_vale_para_a(dos):
    client, _, b = dos

    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"]))


async def test_24_con_el_acceso_caducado_su_usuario_sigue_contando(dos):
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


async def test_25_solo_con_la_de_refresh(dos):
    client, a, b = dos
    client.cookies.delete("access_token")

    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"]))
    assert not _es_rechazo_csrf(await _toca_el_perfil(client, a["csrf_token"]))


async def test_26_sin_sesion_queda_el_double_submit_de_siempre(client: AsyncClient):
    client.cookies.clear()

    respuesta = await _toca_el_perfil(client, secrets.token_urlsafe(32))

    assert not _es_rechazo_csrf(respuesta)
    assert respuesta.status_code == status.HTTP_401_UNAUTHORIZED


async def test_27_vincular_google_ya_no_esta_exenta(dos):
    client, _, _ = dos

    respuesta = await client.post(
        "/api/v1/auth/google/link", json={"code": "x", "redirect_uri": "http://x"}
    )

    assert _es_rechazo_csrf(respuesta)


async def test_28_tras_renovar_vale_el_token_nuevo(dos):
    client, a, _ = dos
    renovada = await client.post("/api/v1/auth/refresh-token")
    assert renovada.status_code == status.HTTP_200_OK, renovada.text
    nuevo = renovada.json()["csrf_token"]

    assert nuevo != a["csrf_token"]
    respuesta = await _toca_el_perfil(client, nuevo)
    assert respuesta.status_code == status.HTTP_200_OK, respuesta.text


async def test_29_por_bearer_sin_cookies_de_sesion(dos):
    client, a, b = dos
    client.cookies.delete("access_token")
    client.cookies.delete("refresh_token")
    bearer = {"Authorization": f"Bearer {a['access_token']}"}

    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"], headers=bearer))
    respuesta = await _toca_el_perfil(client, a["csrf_token"], headers=bearer)
    assert respuesta.status_code == status.HTTP_200_OK, respuesta.text


async def test_30_un_jwt_de_acceso_falso_no_cuenta(dos):
    client, _, b = dos
    falso = jwt.encode(
        {"sub": b["user"]["id"], "type": "access"}, "no-es-la-clave", algorithm=settings.ALGORITHM
    )
    client.cookies.set("access_token", falso)

    # El falso dice B, pero no se cree: manda la de refresh, que es de A
    assert _es_rechazo_csrf(await _toca_el_perfil(client, b["csrf_token"]))
