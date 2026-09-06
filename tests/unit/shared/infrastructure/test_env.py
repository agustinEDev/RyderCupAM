"""
Tests de `env_int`.

Lo que protegen: estas variables se leen al importar, así que un valor mal puesto no
puede tumbar el arranque del contenedor. Cada caso de aquí es una forma real de
equivocarse al escribirlas en el panel de Render.
"""

import pytest

from src.shared.infrastructure.env import env_int


def test_returns_the_default_when_the_variable_is_not_set(monkeypatch):
    monkeypatch.delenv("SOME_LIMIT", raising=False)

    assert env_int("SOME_LIMIT", default=5) == 5


@pytest.mark.parametrize("raw", ["", "   "])
def test_returns_the_default_when_the_variable_is_blank(monkeypatch, raw):
    """Vaciar la variable es la forma natural de 'desactivarla' en Render."""
    monkeypatch.setenv("SOME_LIMIT", raw)

    assert env_int("SOME_LIMIT", default=5) == 5


def test_returns_the_default_when_the_value_is_not_a_number(monkeypatch):
    monkeypatch.setenv("SOME_LIMIT", "dos")

    assert env_int("SOME_LIMIT", default=5) == 5


@pytest.mark.parametrize("raw", ["0", "-3"])
def test_returns_the_default_when_the_value_is_below_the_minimum(monkeypatch, raw):
    """`BCRYPT_MAX_CONCURRENCY=0` reventaría el ThreadPoolExecutor al importar."""
    monkeypatch.setenv("SOME_LIMIT", raw)

    assert env_int("SOME_LIMIT", default=5) == 5


def test_returns_the_configured_value(monkeypatch):
    monkeypatch.setenv("SOME_LIMIT", "12")

    assert env_int("SOME_LIMIT", default=5) == 12


def test_accepts_a_custom_minimum(monkeypatch):
    monkeypatch.setenv("SOME_LIMIT", "1")

    assert env_int("SOME_LIMIT", default=10, minimum=4) == 10
