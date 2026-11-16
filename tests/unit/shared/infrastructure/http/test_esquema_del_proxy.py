"""
La redirección de la barra final no baja a http:// (P-03, auditoría del 16 nov 2026).

`GET https://api.rydercupfriends.com/api/v1/countries/` contestaba `307 Location:
http://api.../countries`: uvicorn corre sin `--proxy-headers`, así que la app cree que la
petición llegó por http (Render termina el TLS). Activar `--proxy-headers` arreglaría el
esquema pero también cambiaría `request.client` con X-Forwarded-For, y la IP del cliente
se decide en un solo sitio (ADR-038, `cloudflare_client_ip`). Este middleware solo mira
`X-Forwarded-Proto` y solo SUBE a https: nunca baja de https a http ni toca el cliente.

| Caso | Petición                                                  | Esperado                     |
|------|-----------------------------------------------------------|------------------------------|
| E1   | /countries/ por http con X-Forwarded-Proto: https         | 307 a https://               |
| E2   | /countries/ por http sin la cabecera (local)              | 307 a http://, como antes    |
| E3   | por https con X-Forwarded-Proto: http (falso)             | sigue https: nunca baja      |
| E4   | «HTTPS», « https » o «https, http» (lista de proxies)     | https (el primero manda)     |
| E5   | X-Forwarded-For en la petición                            | el cliente no cambia         |
| E6   | un websocket con X-Forwarded-Proto: https                 | wss                          |
| E7   | lo que no es HTTP ni websocket (el lifespan)              | pasa sin mirar               |
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

import main
from src.shared.infrastructure.http.esquema_del_proxy import EsquemaDelProxy


@pytest.fixture
def cliente():
    return TestClient(main.app, raise_server_exceptions=False)


def _scope_visto(scope: dict) -> dict:
    """El scope con el que el middleware llama a la app envuelta."""
    visto: dict = {}

    async def app(scope, receive, send):
        visto.update(scope)

    asyncio.run(EsquemaDelProxy(app)(scope, None, None))
    return visto


def _scope(tipo="http", esquema="http", proto: bytes | None = None, **extra) -> dict:
    cabeceras = [(b"host", b"api.example.com")]
    if proto is not None:
        cabeceras.append((b"x-forwarded-proto", proto))
    return {"type": tipo, "scheme": esquema, "headers": cabeceras, **extra}


def test_the_trailing_slash_redirect_keeps_https_behind_the_proxy(cliente):
    """
    Given: la app tras el proxy de Render, que habla http con ella
    When: se pide /api/v1/countries/ con X-Forwarded-Proto: https (E1)
    Then: la redirección apunta a https://
    """
    respuesta = cliente.get(
        "/api/v1/countries/", headers={"X-Forwarded-Proto": "https"}, follow_redirects=False
    )

    assert respuesta.status_code == 307
    assert respuesta.headers["location"].startswith("https://testserver/api/v1/countries")


def test_without_the_header_the_redirect_is_unchanged(cliente):
    """
    Given: la app en local, sin proxy
    When: se pide /api/v1/countries/ sin X-Forwarded-Proto (E2)
    Then: la redirección sigue en http://, como antes
    """
    respuesta = cliente.get("/api/v1/countries/", follow_redirects=False)

    assert respuesta.status_code == 307
    assert respuesta.headers["location"].startswith("http://testserver/api/v1/countries")


def test_a_forged_http_never_downgrades_https():
    """
    Given: una petición que llega por https
    When: trae X-Forwarded-Proto: http (E3)
    Then: sigue en https
    """
    assert _scope_visto(_scope(esquema="https", proto=b"http"))["scheme"] == "https"


@pytest.mark.parametrize("proto", [b"HTTPS", b" https ", b"https, http", b"https,http"])
def test_the_first_proto_of_the_list_decides(proto):
    """
    Given: X-Forwarded-Proto con mayúsculas, espacios o una lista de proxies (E4)
    When: la petición pasa por el middleware
    Then: https
    """
    assert _scope_visto(_scope(proto=proto))["scheme"] == "https"


@pytest.mark.parametrize("proto", [b"http", b"ftp", b"", b"http, https"])
def test_anything_but_https_first_leaves_the_scheme(proto):
    """
    Given: X-Forwarded-Proto que no empieza por https
    When: la petición pasa por el middleware
    Then: el esquema no cambia
    """
    assert _scope_visto(_scope(proto=proto))["scheme"] == "http"


def test_the_client_address_is_never_touched():
    """
    Given: una petición con X-Forwarded-Proto y X-Forwarded-For (E5)
    When: pasa por el middleware
    Then: el cliente es el mismo par (IP, puerto) del socket
    """
    scope = _scope(proto=b"https", client=("10.0.0.7", 4321))
    scope["headers"].append((b"x-forwarded-for", b"203.0.113.9"))

    visto = _scope_visto(scope)

    assert visto["client"] == ("10.0.0.7", 4321)
    assert visto["scheme"] == "https"


def test_a_websocket_becomes_wss():
    """
    Given: un websocket tras el proxy (E6)
    When: trae X-Forwarded-Proto: https
    Then: su esquema es wss
    """
    assert _scope_visto(_scope(tipo="websocket", esquema="ws", proto=b"https"))["scheme"] == "wss"


def test_the_lifespan_passes_untouched():
    """
    Given: un scope que no es HTTP ni websocket (E7)
    When: pasa por el middleware
    Then: llega igual a la app
    """
    scope = {"type": "lifespan"}

    assert _scope_visto(scope) == {"type": "lifespan"}


def test_the_caller_scope_is_not_mutated():
    """
    Given: el scope de una petición
    When: el middleware cambia el esquema
    Then: lo hace en una copia, sin tocar el scope original
    """
    scope = _scope(proto=b"https")

    _scope_visto(scope)

    assert scope["scheme"] == "http"
