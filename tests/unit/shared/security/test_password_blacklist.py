"""La lista de contraseñas comunes se compara sin distinguir mayúsculas (BE #518)."""

import pytest

from src.modules.user.domain.value_objects.password import InvalidPasswordError, Password
from src.shared.security.password_blacklist import COMMON_PASSWORDS, is_common_password


@pytest.mark.parametrize("entrada", sorted(COMMON_PASSWORDS))
def test_toda_entrada_de_la_lista_se_rechaza(entrada):
    """Las escritas con mayúscula («Password123!») no coincidían nunca: se compara en minúsculas."""
    assert is_common_password(entrada)


@pytest.mark.parametrize(
    "variante", ["Password123!", "password123!", "PASSWORD123!", "pAsSwOrD123!"]
)
def test_da_igual_como_se_escriba(variante):
    assert is_common_password(variante)


def test_una_que_solo_contiene_una_palabra_comun_vale():
    assert not is_common_password("MiPassword123!Larga")


def test_el_registro_rechaza_password123_con_el_motivo():
    """Cumple el resto de la política, así que solo la para la lista: antes se registraba."""
    with pytest.raises(InvalidPasswordError, match="demasiado común"):
        Password.from_plain_text("Password123!")
