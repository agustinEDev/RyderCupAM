"""
La IP real del cliente, solo cuando la petición viene de Cloudflare (BE #466).

Cloudflare pone la IP del cliente en `CF-Connecting-IP` y una regla suya añade
`X-Origin-Verify` con un secreto que solo conocen Cloudflare y la API
(`CLOUDFLARE_ORIGIN_SECRET`). Sin ese secreto, la cabecera la puede escribir
cualquiera que llame directo al origen de Render, así que no se cree: se cae al
contador compartido de hoy (ADR-038), nunca a uno elegido por quien llama.
"""

import pytest
from starlette.requests import Request

from src.config.rate_limit import get_client_identifier
from src.shared.infrastructure.http.http_context_validator import (
    cloudflare_client_ip,
    get_trusted_client_ip,
)

SECRETO = "s3creto-de-prueba-0123456789abcdef"
PEER = "10.20.30.40"


def _request(headers: dict[str, str | bytes] | None = None, peer: str = PEER) -> Request:
    """Una petición que llega desde `peer` con estas cabeceras."""
    crudas = [
        (k.lower().encode("latin-1"), v if isinstance(v, bytes) else v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "query_string": b"",
            "headers": crudas,
            "client": (peer, 12345),
        }
    )


def _de_cloudflare(ip: str, secreto: str = SECRETO, **mas: str) -> Request:
    """Lo que manda Cloudflare: la IP del cliente y el secreto de su regla."""
    return _request({"CF-Connecting-IP": ip, "X-Origin-Verify": secreto, **mas})


@pytest.fixture(autouse=True)
def _produccion_con_secreto(monkeypatch):
    """Producción, con el secreto configurado en Render."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", SECRETO)


def test_rate_limit_key_with_valid_origin_secret_uses_cloudflare_ipv4():
    """
    Given: Producción, el secreto correcto y CF-Connecting-IP con una IPv4
    When: Se calcula la clave de red
    Then: Es esa IPv4, no la del proxy
    """
    assert get_client_identifier(_de_cloudflare("203.0.113.7")) == "203.0.113.7"


def test_rate_limit_key_with_wrong_origin_secret_falls_back_to_peer():
    """
    Given: Producción y un secreto que no es el configurado
    When: Se calcula la clave de red
    Then: Es la IP del proxy, el contador compartido de hoy
    """
    assert get_client_identifier(_de_cloudflare("203.0.113.7", secreto="otro")) == PEER


def test_rate_limit_key_with_forged_cf_ip_and_no_secret_falls_back_to_peer():
    """
    Given: Producción y una CF-Connecting-IP sin X-Origin-Verify (llamada directa al origen)
    When: Se calcula la clave de red
    Then: Se ignora la cabecera y cuenta la IP del proxy
    """
    assert get_client_identifier(_request({"CF-Connecting-IP": "203.0.113.7"})) == PEER


@pytest.mark.parametrize("ip", ["", "   ", "no-es-una-ip", "999.1.1.1", "1.2.3.4, 5.6.7.8"])
def test_rate_limit_key_with_valid_secret_and_bad_cf_ip_falls_back_to_peer(ip):
    """
    Given: Producción, el secreto correcto y una CF-Connecting-IP vacía o inválida
    When: Se calcula la clave de red
    Then: Cuenta la IP del proxy
    """
    assert get_client_identifier(_de_cloudflare(ip)) == PEER


@pytest.mark.parametrize("configurado", [None, ""])
def test_rate_limit_key_without_configured_secret_never_trusts_cloudflare(monkeypatch, configurado):
    """
    Given: Producción sin CLOUDFLARE_ORIGIN_SECRET (o vacío) y una cabecera vacía
    When: Se calcula la clave de red
    Then: Cuenta la IP del proxy: un secreto vacío no coincide con una cabecera vacía
    """
    if configurado is None:
        monkeypatch.delenv("CLOUDFLARE_ORIGIN_SECRET", raising=False)
    else:
        monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", configurado)

    assert get_client_identifier(_de_cloudflare("203.0.113.7", secreto="")) == PEER


def test_rate_limit_key_groups_ipv6_by_its_64_prefix():
    """
    Given: Dos IPv6 del mismo /64 y una de otro /64
    When: Se calcula la clave de red de cada una
    Then: Las dos del mismo /64 comparten clave y la otra no: rotar dentro del /64 no da contadores nuevos
    """
    una = get_client_identifier(_de_cloudflare("2001:db8:aaaa:1::1"))
    vecina = get_client_identifier(_de_cloudflare("2001:db8:aaaa:1:ffff:ffff:ffff:ffff"))
    otra = get_client_identifier(_de_cloudflare("2001:db8:aaaa:2::1"))

    assert una == vecina == "2001:db8:aaaa:1::/64"
    assert otra != una


def test_rate_limit_key_treats_ipv4_mapped_ipv6_as_ipv4():
    """
    Given: Una IPv4 escrita como IPv6 mapeada (::ffff:1.2.3.4)
    When: Se calcula la clave de red
    Then: Es la IPv4, la misma que si llegara escrita normal
    """
    assert get_client_identifier(_de_cloudflare("::ffff:198.51.100.9")) == "198.51.100.9"


@pytest.mark.parametrize("valor", ["ñandú".encode(), b"\xff\xfe", SECRETO.upper().encode()])
def test_origin_secret_comparison_rejects_odd_values_without_raising(valor):
    """
    Given: Un X-Origin-Verify con bytes no ASCII, basura o el secreto en mayúsculas
    When: Se busca la IP de Cloudflare
    Then: No hay IP de Cloudflare y no se lanza nada
    """
    peticion = _request({"CF-Connecting-IP": "203.0.113.7", "X-Origin-Verify": valor})

    assert cloudflare_client_ip(peticion) is None
    assert get_client_identifier(peticion) == PEER


def test_origin_secret_comparison_is_constant_time(monkeypatch):
    """
    Given: El secreto correcto
    When: Se busca la IP de Cloudflare
    Then: La comparación pasa por hmac.compare_digest, no por ==
    """
    from src.shared.infrastructure.http import http_context_validator

    llamadas = []
    original = http_context_validator.hmac.compare_digest

    def espia(a, b):
        """Apunta la llamada y compara como la real."""
        llamadas.append((a, b))
        return original(a, b)

    monkeypatch.setattr(http_context_validator.hmac, "compare_digest", espia)

    assert cloudflare_client_ip(_de_cloudflare("203.0.113.7")) == "203.0.113.7"
    assert llamadas


def test_rate_limit_key_outside_production_keeps_test_client_id(monkeypatch):
    """
    Given: Fuera de producción, con X-Test-Client-ID y además una petición de Cloudflare válida
    When: Se calcula la clave de red
    Then: Manda X-Test-Client-ID, como hasta ahora
    """
    monkeypatch.setenv("ENVIRONMENT", "development")
    peticion = _de_cloudflare("203.0.113.7", **{"X-Test-Client-ID": "cliente-de-test"})

    assert get_client_identifier(peticion) == "cliente-de-test"


def test_audit_ip_with_valid_origin_secret_is_the_full_cloudflare_address():
    """
    Given: El secreto correcto y una IPv6 en CF-Connecting-IP
    When: Se saca la IP de auditoría y del dispositivo
    Then: Es la dirección completa (no el /64), aunque TRUST_CLOUDFLARE_HEADERS esté apagado
    """
    ip = get_trusted_client_ip(
        _de_cloudflare("2001:db8:aaaa:1::42", **{"X-Forwarded-For": "6.6.6.6"}),
        ["10.0.0.0/8"],
        False,
    )

    assert ip == "2001:db8:aaaa:1::42"


def test_audit_ip_without_origin_secret_keeps_todays_forwarded_for_logic():
    """
    Given: Sin el secreto, desde un proxy de confianza y con X-Forwarded-For
    When: Se saca la IP de auditoría
    Then: La primera de X-Forwarded-For, como hoy: las huellas de los dispositivos no cambian
    """
    peticion = _request(
        {"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "198.51.100.1, 10.1.1.1"}
    )

    assert get_trusted_client_ip(peticion, ["10.0.0.0/8"], False) == "198.51.100.1"


def test_audit_ip_with_ipv4_mapped_cloudflare_address_is_ipv4():
    """
    Given: El secreto correcto y una IPv4 mapeada en CF-Connecting-IP
    When: Se saca la IP de auditoría
    Then: Es la IPv4
    """
    assert get_trusted_client_ip(_de_cloudflare("::ffff:198.51.100.9"), [], False) == "198.51.100.9"


@pytest.mark.parametrize("rara", ["0.0.0.0", "127.0.0.1", "127.0.0.2", "::", "::1", "fe80::1%eth0"])
def test_cloudflare_ip_that_is_a_sentinel_or_loopback_is_not_trusted(rara):
    """
    Given: El secreto correcto y una CF-Connecting-IP que no es de un cliente real
    When: Se busca la IP de Cloudflare y la de red
    Then: No hay IP de Cloudflare y cuenta la del proxy: la auditoría no guarda 0.0.0.0,
          un bucle local ni una zona IPv6 (revisor, 5 nov)
    """
    peticion = _de_cloudflare(rara)

    assert cloudflare_client_ip(peticion) is None
    assert get_client_identifier(peticion) == PEER


def test_startup_reports_whether_the_origin_secret_is_configured_without_its_value(caplog):
    """
    Given: El secreto configurado
    When: Arranca la app y lo comprueba
    Then: Dice que está configurado, sin el valor ni nada sacado de él (CodeQL,
          py/clear-text-logging-sensitive-data), y sin avisos
    """
    import logging

    from src.shared.infrastructure.http.http_context_validator import (
        informa_del_secreto_de_origen,
    )

    with caplog.at_level(logging.INFO):
        informa_del_secreto_de_origen()

    assert SECRETO not in caplog.text
    assert str(len(SECRETO)) not in caplog.text
    assert "configurada" in caplog.text
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)


@pytest.mark.parametrize("pegado", [f" {SECRETO}", f"{SECRETO}\n", f"{SECRETO} "])
def test_startup_warns_when_the_origin_secret_has_surrounding_whitespace(
    monkeypatch, caplog, pegado
):
    """
    Given: El secreto pegado con un espacio o un salto de línea de más
    When: Arranca la app y lo comprueba
    Then: Avisa con un warning, sin el valor: nunca coincidiría con el de Cloudflare
          y todo caería en silencio al contador compartido (revisor, 5 nov)
    """
    import logging

    from src.shared.infrastructure.http.http_context_validator import (
        informa_del_secreto_de_origen,
    )

    monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", pegado)
    with caplog.at_level(logging.INFO):
        informa_del_secreto_de_origen()

    assert SECRETO not in caplog.text
    assert any(
        r.levelno == logging.WARNING and "espacios" in r.getMessage() for r in caplog.records
    )


def test_startup_warns_when_the_origin_secret_is_missing_in_production(monkeypatch, caplog):
    """
    Given: Producción sin CLOUDFLARE_ORIGIN_SECRET
    When: Arranca la app y lo comprueba
    Then: Avisa con un warning: sin él, los límites anónimos son de toda la app
    """
    import logging

    from src.shared.infrastructure.http.http_context_validator import (
        informa_del_secreto_de_origen,
    )

    monkeypatch.delenv("CLOUDFLARE_ORIGIN_SECRET", raising=False)
    with caplog.at_level(logging.INFO):
        informa_del_secreto_de_origen()

    assert any(r.levelno == logging.WARNING for r in caplog.records)
