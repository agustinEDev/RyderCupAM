"""La lista de contraseñas comunes se compara sin distinguir mayúsculas (BE #518)."""

import pytest

from src.shared.security.password_blacklist import _ENTRIES, COMMON_PASSWORDS, is_common_password


@pytest.mark.parametrize("entrada", sorted(_ENTRIES))
def test_toda_entrada_de_la_lista_se_rechaza(entrada):
    """
    Given cada entrada tal como está escrita en la lista
    When se comprueba
    Then se rechaza: las de mayúscula («Password123!») no coincidían nunca
    """
    assert is_common_password(entrada)


def test_la_lista_publica_es_la_normalizada():
    """Una sola fuente: lo que se expone es lo que se aplica, sin duplicados por mayúsculas."""
    assert all(entrada == entrada.casefold() for entrada in COMMON_PASSWORDS)
    assert len(COMMON_PASSWORDS) == len({entrada.casefold() for entrada in _ENTRIES})


@pytest.mark.parametrize(
    "variante", ["Password123!", "password123!", "PASSWORD123!", "pAsSwOrD123!"]
)
def test_da_igual_como_se_escriba(variante):
    """Given una entrada con otras mayúsculas When se comprueba Then se rechaza."""
    assert is_common_password(variante)


def test_una_que_solo_contiene_una_palabra_comun_vale():
    """Given una que solo CONTIENE una común When se comprueba Then vale: se compara entera."""
    assert not is_common_password("MiPassword123!Larga")
