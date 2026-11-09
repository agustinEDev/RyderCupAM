"""
La contraseña se calcula con el hasher que instala la composition root (auditoría
de arquitectura del 9 nov 2026, B2): el dominio ya no importa bcrypt ni lee
variables de entorno para decidir cuántas rondas usar.
"""

import pytest

from src.modules.user.domain.services import password_hasher
from src.modules.user.domain.services.password_hasher import (
    HasherNoInstaladoError,
    hasher_de_contrasenas,
    instala_el_hasher,
)
from src.modules.user.domain.value_objects.password import Password

VALIDA = "V@l1dP@ss123!"


class HasherDePrueba:
    """Un hasher que deja rastro de lo que se le pide."""

    def __init__(self) -> None:
        """Sin pedidos todavía."""
        self.pedidos: list[str] = []

    def hash(self, plain: str) -> str:
        """Un hash falso que se reconoce a la vista."""
        self.pedidos.append(plain)
        return f"falso:{plain}"

    def matches(self, plain: str, hashed: str) -> bool:
        """Casa si el hash es el falso de esa contraseña."""
        return hashed == f"falso:{plain}"


@pytest.fixture
def hasher_cambiado():
    """Instala uno de prueba y deja el que había al acabar."""
    anterior = password_hasher._instalado
    nuevo = HasherDePrueba()
    instala_el_hasher(nuevo)
    Password._relleno.cache_clear()
    try:
        yield nuevo
    finally:
        password_hasher._instalado = anterior
        Password._relleno.cache_clear()


def test_without_a_hasher_creating_a_password_fails_closed():
    """
    Given: nadie ha instalado un hasher
    When: se crea una contraseña desde texto plano
    Then: falla con HasherNoInstaladoError, en vez de guardar algo sin proteger
    """
    anterior = password_hasher._instalado
    password_hasher._instalado = None
    try:
        with pytest.raises(HasherNoInstaladoError):
            Password.from_plain_text(VALIDA)
        with pytest.raises(HasherNoInstaladoError):
            hasher_de_contrasenas()
    finally:
        password_hasher._instalado = anterior


def test_the_password_is_hashed_by_the_installed_hasher(hasher_cambiado):
    """
    Given: un hasher instalado
    When: se crea una contraseña y se comprueba
    Then: el hash y la comprobación los hace ese hasher
    """
    contrasena = Password.from_plain_text(VALIDA)

    assert contrasena.hashed_value == f"falso:{VALIDA}"
    assert contrasena.verify(VALIDA) is True
    assert contrasena.verify("Otra-Cosa-123!") is False
    assert hasher_cambiado.pedidos == [VALIDA]


def test_the_dummy_hash_uses_the_installed_hasher_and_always_says_no(hasher_cambiado):
    """
    Given: un hasher instalado
    When: se verifica contra el relleno (login con un correo que no existe)
    Then: lo calcula ese hasher (mismo coste que uno real) y la respuesta es no
    """
    assert Password.verifica_contra_el_relleno(VALIDA) is False
    assert len(hasher_cambiado.pedidos) == 1


def test_a_hasher_error_on_verify_is_a_no(hasher_cambiado):
    """
    Given: un hasher que revienta al comprobar
    When: se verifica una contraseña
    Then: la respuesta es no, como antes con un error de bcrypt
    """
    contrasena = Password.from_plain_text(VALIDA)

    def revienta(plain: str, hashed: str) -> bool:
        """Ayudante del test: falla como un hash corrupto."""
        raise ValueError("hash corrupto")

    hasher_cambiado.matches = revienta

    assert contrasena.verify(VALIDA) is False
