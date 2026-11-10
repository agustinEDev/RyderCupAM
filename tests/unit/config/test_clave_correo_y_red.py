"""
La clave del freno de «Olvidé mi contraseña» por correo + red (fase 3, H1).

Como el freno del login (ADR-043): tres peticiones ajenas desde otra red ya no dejan al
dueño sin poder pedir su enlace.
"""

from src.config.rate_limit import email_and_network_rate_limit_key, email_rate_limit_key


def test_h1_same_email_and_network_same_key():
    """Mismo correo (normalizado) y misma red: la misma clave."""
    assert email_and_network_rate_limit_key(
        "Ana@Example.com", "203.0.113.7"
    ) == email_and_network_rate_limit_key("ana@example.com", "203.0.113.7")


def test_h1_another_network_another_key():
    """Mismo correo desde otra red: otra clave."""
    assert email_and_network_rate_limit_key(
        "ana@example.com", "203.0.113.7"
    ) != email_and_network_rate_limit_key("ana@example.com", "198.51.100.9")


def test_h1_another_email_another_key():
    """Otro correo desde la misma red: otra clave."""
    assert email_and_network_rate_limit_key(
        "ana@example.com", "203.0.113.7"
    ) != email_and_network_rate_limit_key("luis@example.com", "203.0.113.7")


def test_h1_the_key_keeps_neither_the_email_nor_the_ip_in_clear():
    """Ni el correo ni la IP en claro: la clave puede acabar en un volcado."""
    clave = email_and_network_rate_limit_key("ana@example.com", "203.0.113.7")

    assert "ana@" not in clave and "203.0.113.7" not in clave
    assert clave != email_rate_limit_key("ana@example.com")
