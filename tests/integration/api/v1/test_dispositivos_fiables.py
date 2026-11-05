"""
Dispositivos fiables, fase 1: reconocer y revocar (BE #737, #730).

  #   caso                                                    | esperado
  ----|------------------------------------------------------|--------------------------------
  D1  login                                                   | el access token lleva `did`, el id
                                                              |   del dispositivo
  D2  revocar otro dispositivo                                | su siguiente petición: 401 «revocado»,
                                                              |   aunque cambie de red (sin huella)
  D3  un `did` de otro usuario o que no existe                | 401
  D4  un token sin `did` (anterior a esta versión)            | pasa, como hasta ahora
  D5  cerrar sesión y volver a entrar desde el mismo navegador| el mismo dispositivo, sin duplicado
  D6  el refresco                                             | renueva la cookie del dispositivo y
                                                              |   el `did` del token nuevo
  D7  dos cuentas en el mismo navegador                       | cada una conserva su dispositivo
  D8  el navegador se actualiza (otro user-agent)             | el mismo dispositivo, con el nuevo
  D9  la app instalada y Safari en el mismo móvil y red       | dos dispositivos distintos
  D10 verificar el email abre sesión                          | con dispositivo y refresco que funciona
  D11 una petición con el dispositivo revocado, cambiando de red| 401 igual: revocar no depende de la IP
"""

import uuid

import jwt
import pytest
from fastapi import status
from httpx import AsyncClient

from src.config.settings import settings
from tests.conftest import get_user_by_email

pytestmark = pytest.mark.asyncio

CLAVE = "V@l1dP@ss123!"
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
)
SAFARI_IPHONE_NUEVO = SAFARI_IPHONE.replace("18_1", "18_2").replace("18.1", "18.2")
SAFARI_MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.1 Safari/605.1.15"
)


def _otro(client: AsyncClient) -> AsyncClient:
    """Otro navegador contra la misma API y la misma base de datos: cookies propias."""
    return AsyncClient(transport=client._transport, base_url=client.base_url)


SECRETO = "secreto-de-los-tests-de-dispositivos"
# Cada red, su IP real: llega por Cloudflare con el secreto, como en producción
IPS = {
    "red-casa": "203.0.113.10",
    "red-movil": "198.51.100.20",
    "red-oficina": "192.0.2.30",
    "red-1": "203.0.113.41",
    "red-2": "198.51.100.42",
    "red-3": "192.0.2.43",
}


@pytest.fixture(autouse=True)
def _cloudflare(monkeypatch):
    """El secreto de Cloudflare configurado: la IP de cada red es la de verdad."""
    monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", SECRETO)


def _cabeceras(ua: str, red: str = "red-casa", modo: str | None = None) -> dict:
    cabeceras = {
        "User-Agent": ua,
        "X-Test-Client-ID": red,
        "CF-Connecting-IP": IPS[red],
        "X-Origin-Verify": SECRETO,
    }
    if modo:
        cabeceras["X-App-Mode"] = modo
    return cabeceras


async def _registra(client: AsyncClient, email: str) -> None:
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": CLAVE,
            "first_name": "Ana",
            "last_name": "Golf",
            "accept_terms": True,
        },
    )
    assert r.status_code == status.HTTP_201_CREATED, r.text


async def _entra(
    c: AsyncClient, email: str, ua: str, red: str = "red-casa", modo: str | None = None
):
    r = await c.post(
        "/api/v1/auth/login",
        json={"email": email, "password": CLAVE},
        headers=_cabeceras(ua, red, modo),
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    return r


def _did(c: AsyncClient) -> str | None:
    payload = jwt.decode(
        c.cookies.get("access_token"), settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    return payload.get("did")


async def _mis_dispositivos(c: AsyncClient, ua: str, red: str = "red-casa") -> list[dict]:
    r = await c.get("/api/v1/users/me/devices", headers=_cabeceras(ua, red))
    assert r.status_code == status.HTTP_200_OK, r.text
    return r.json()["devices"]


async def test_d1_login_puts_the_device_id_in_the_access_token(client: AsyncClient):
    """
    Given: Un usuario que entra desde un iPhone
    When: Mira su access token
    Then: Lleva `did`, el id del dispositivo que se dio de alta
    """
    email = f"d1-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    r = await _entra(client, email, SAFARI_IPHONE)

    assert _did(client) == r.json()["device_id"]


async def test_d2_d11_revoked_device_gets_401_on_next_request_even_on_another_network(
    client: AsyncClient,
):
    """
    Given: El mismo usuario en un iPhone y en un Mac
    When: Desde el Mac revoca el iPhone, y el iPhone pide algo desde otra red
    Then: 401 «Dispositivo revocado» al momento: revocar no depende de la huella ni de la IP
    """
    email = f"d2-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    iphone, mac = _otro(client), _otro(client)
    await _entra(iphone, email, SAFARI_IPHONE, red="red-casa")
    await _entra(mac, email, SAFARI_MAC, red="red-oficina")
    did_iphone = _did(iphone)

    csrf = mac.cookies.get("csrf_token")
    r = await mac.delete(
        f"/api/v1/users/me/devices/{did_iphone}",
        headers={**_cabeceras(SAFARI_MAC, "red-oficina"), "X-CSRF-Token": csrf},
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    r = await iphone.get(
        "/api/v1/users/me/devices", headers=_cabeceras(SAFARI_IPHONE, red="red-movil")
    )
    assert r.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revocado" in r.json()["detail"].lower()
    # El Mac sigue dentro
    assert (
        await mac.get("/api/v1/users/me/devices", headers=_cabeceras(SAFARI_MAC, "red-oficina"))
    ).status_code == 200


async def test_d3_did_of_another_user_or_missing_is_rejected(client: AsyncClient):
    """
    Given: Un access token bien firmado con el `did` de otro usuario, o de un dispositivo que no existe
    When: Se usa
    Then: 401: el dispositivo tiene que ser del usuario y existir
    """
    email_a = f"d3a-{uuid.uuid4().hex[:6]}@example.com"
    email_b = f"d3b-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email_a)
    await _registra(client, email_b)
    a, b = _otro(client), _otro(client)
    await _entra(a, email_a, SAFARI_IPHONE)
    await _entra(b, email_b, SAFARI_MAC)
    sub_a = jwt.decode(
        a.cookies.get("access_token"), settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )["sub"]

    for did in (_did(b), str(uuid.uuid4())):
        from src.shared.infrastructure.security.jwt_handler import create_access_token

        falso = create_access_token({"sub": sub_a, "did": did})
        r = await client.get(
            "/api/v1/users/me/devices",
            cookies={"access_token": falso},
            headers=_cabeceras(SAFARI_IPHONE),
        )
        assert r.status_code == status.HTTP_401_UNAUTHORIZED, did


async def test_d4_token_without_did_still_works(client: AsyncClient):
    """
    Given: Un access token sin `did`, como los emitidos antes de esta versión
    When: Se usa
    Then: Pasa: dura 15 minutos y el siguiente refresco ya trae `did`
    """
    email = f"d4-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    c = _otro(client)
    await _entra(c, email, SAFARI_IPHONE)
    sub = jwt.decode(
        c.cookies.get("access_token"), settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )["sub"]
    from src.shared.infrastructure.security.jwt_handler import create_access_token

    viejo = create_access_token({"sub": sub})
    r = await client.get(
        "/api/v1/users/me/devices",
        cookies={"access_token": viejo},
        headers=_cabeceras(SAFARI_IPHONE),
    )

    assert r.status_code == status.HTTP_200_OK, r.text


async def test_d5_logout_and_login_again_keeps_the_same_device(client: AsyncClient):
    """
    Given: Un iPhone con su dispositivo
    When: Cierra sesión y vuelve a entrar desde otra red
    Then: Es el mismo dispositivo y no aparece otro: el logout no borra la cookie que lo reconoce
    """
    email = f"d5-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    c = _otro(client)
    primero = (await _entra(c, email, SAFARI_IPHONE, red="red-casa")).json()["device_id"]
    r = await c.post("/api/v1/auth/logout", json={}, headers=_cabeceras(SAFARI_IPHONE))
    assert r.status_code == status.HTTP_200_OK

    segundo = (await _entra(c, email, SAFARI_IPHONE, red="red-movil")).json()["device_id"]

    assert segundo == primero
    assert len(await _mis_dispositivos(c, SAFARI_IPHONE, "red-movil")) == 1


async def test_d6_refresh_renews_the_device_cookie_and_the_did(client: AsyncClient):
    """
    Given: Una sesión en un iPhone
    When: Se refresca
    Then: La respuesta vuelve a poner la cookie del dispositivo (Safari no la deja caducar) y el token nuevo lleva `did`
    """
    email = f"d6-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    c = _otro(client)
    dispositivo = (await _entra(c, email, SAFARI_IPHONE)).json()["device_id"]

    r = await c.post("/api/v1/auth/refresh-token", headers=_cabeceras(SAFARI_IPHONE))

    assert r.status_code == status.HTTP_200_OK, r.text
    puestas = [
        v for k, v in r.headers.multi_items() if k == "set-cookie" and v.startswith("device_id=")
    ]
    assert puestas and dispositivo in puestas[0]
    assert _did(c) == dispositivo


async def test_d7_two_accounts_in_the_same_browser_keep_their_devices(client: AsyncClient):
    """
    Given: Un navegador donde entran por turnos dos cuentas
    When: Entra A, luego B, y otra vez A
    Then: A vuelve a su mismo dispositivo: la cookie guarda los de las dos cuentas
    """
    email_a = f"d7a-{uuid.uuid4().hex[:6]}@example.com"
    email_b = f"d7b-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email_a)
    await _registra(client, email_b)
    c = _otro(client)
    de_a = (await _entra(c, email_a, SAFARI_MAC, red="red-1")).json()["device_id"]
    await c.post("/api/v1/auth/logout", json={}, headers=_cabeceras(SAFARI_MAC, "red-1"))
    await _entra(c, email_b, SAFARI_MAC, red="red-2")
    await c.post("/api/v1/auth/logout", json={}, headers=_cabeceras(SAFARI_MAC, "red-2"))

    otra_vez_a = (await _entra(c, email_a, SAFARI_MAC, red="red-3")).json()["device_id"]

    assert otra_vez_a == de_a


async def test_d8_browser_update_keeps_the_device_and_stores_the_new_user_agent(
    client: AsyncClient,
):
    """
    Given: Un iPhone con iOS 18.1
    When: Se actualiza a 18.2 y vuelve a entrar
    Then: Es el mismo dispositivo y guarda el user-agent nuevo
    """
    email = f"d8-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    c = _otro(client)
    primero = (await _entra(c, email, SAFARI_IPHONE)).json()["device_id"]
    await c.post("/api/v1/auth/logout", json={}, headers=_cabeceras(SAFARI_IPHONE))

    segundo = (await _entra(c, email, SAFARI_IPHONE_NUEVO)).json()["device_id"]
    dispositivos = await _mis_dispositivos(c, SAFARI_IPHONE_NUEVO)

    assert segundo == primero
    assert len(dispositivos) == 1
    assert dispositivos[0]["user_agent"] == SAFARI_IPHONE_NUEVO


async def test_d9_installed_app_and_safari_on_the_same_phone_are_two_devices(client: AsyncClient):
    """
    Given: El mismo iPhone, en la misma red: Safari y la app instalada (cookies separadas)
    When: Entra desde los dos
    Then: Son dos dispositivos: la app avisa de que va instalada (X-App-Mode)
    """
    email = f"d9-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    safari, app = _otro(client), _otro(client)
    en_safari = (await _entra(safari, email, SAFARI_IPHONE)).json()["device_id"]
    en_app = (await _entra(app, email, SAFARI_IPHONE, modo="standalone")).json()["device_id"]

    assert en_app != en_safari


async def test_d10_verify_email_opens_a_session_whose_refresh_works(client: AsyncClient):
    """
    Given: Un usuario recién registrado
    When: Verifica su email (la app le deja dentro) y a los 15 minutos se refresca
    Then: El refresco funciona: hay dispositivo y su refresh token está guardado. Antes, a los
          15 minutos le echaban con REFRESH_TOKEN_NOT_FOUND
    """
    email = f"d10-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    usuario = await get_user_by_email(client, email)
    c = _otro(client)

    r = await c.post(
        "/api/v1/auth/verify-email",
        json={"token": usuario.verification_token},
        headers=_cabeceras(SAFARI_IPHONE),
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    assert _did(c)

    r = await c.post("/api/v1/auth/refresh-token", headers=_cabeceras(SAFARI_IPHONE))
    assert r.status_code == status.HTTP_200_OK, r.text


async def test_f3_the_list_describes_each_device_for_the_screen(client: AsyncClient):
    """
    Given: Un iPhone con la app instalada que entra desde España por Cloudflare
    When: Mira su lista de dispositivos
    Then: Lleva tipo, plataforma y navegador, si es la app instalada, el país de Cloudflare,
          la IP con el final tapado y las fechas en UTC con su «Z» (BE #737, fase 3)
    """
    email = f"f3-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    c = _otro(client)
    cabeceras = {**_cabeceras(SAFARI_IPHONE, "red-casa", modo="standalone"), "CF-IPCountry": "ES"}
    r = await c.post(
        "/api/v1/auth/login", json={"email": email, "password": CLAVE}, headers=cabeceras
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    r = await c.get("/api/v1/users/me/devices", headers=cabeceras)
    dispositivo = r.json()["devices"][0]

    assert (dispositivo["device_type"], dispositivo["platform"], dispositivo["browser"]) == (
        "phone",
        "iphone",
        "safari",
    )
    assert dispositivo["installed_app"] is True
    assert dispositivo["country_code"] == "ES"
    assert dispositivo["ip_address"] == "203.0.113.***"
    assert dispositivo["last_used_at"].endswith("Z") and dispositivo["created_at"].endswith("Z")


async def test_f3b_country_is_ignored_without_the_cloudflare_secret(client: AsyncClient):
    """
    Given: Una petición con CF-IPCountry pero sin el secreto de Cloudflare
    When: Entra y mira su lista
    Then: No hay país: esa cabecera la puede escribir cualquiera que llame al origen
    """
    email = f"f3b-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    c = _otro(client)
    cabeceras = {"User-Agent": SAFARI_MAC, "X-Test-Client-ID": "sin-secreto", "CF-IPCountry": "FR"}
    r = await c.post(
        "/api/v1/auth/login", json={"email": email, "password": CLAVE}, headers=cabeceras
    )
    assert r.status_code == status.HTTP_200_OK, r.text

    dispositivo = (await c.get("/api/v1/users/me/devices", headers=cabeceras)).json()["devices"][0]

    assert dispositivo["country_code"] is None


async def test_f3c_a_known_device_gets_its_country_updated(client: AsyncClient):
    """
    Given: Un Mac que entró sin país (sin Cloudflare)
    When: Vuelve a entrar por Cloudflare desde Portugal
    Then: El mismo dispositivo, ahora con país PT
    """
    email = f"f3c-{uuid.uuid4().hex[:6]}@example.com"
    await _registra(client, email)
    c = _otro(client)
    primero = (await _entra(c, email, SAFARI_MAC, "red-casa")).json()["device_id"]
    con_pais = {**_cabeceras(SAFARI_MAC, "red-movil"), "CF-IPCountry": "PT"}
    r = await c.post(
        "/api/v1/auth/login", json={"email": email, "password": CLAVE}, headers=con_pais
    )
    assert r.json()["device_id"] == primero

    dispositivo = (await c.get("/api/v1/users/me/devices", headers=con_pais)).json()["devices"][0]

    assert dispositivo["country_code"] == "PT"
