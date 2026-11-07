"""
El usuario acepta una contraseña ya calculada (BE #283, 7 nov 2026).

El bcrypt se calcula fuera de la transacción y se le entrega después al dominio: con un
`Password` ya hecho, `create`, `change_password` y `reset_password` lo usan tal cual, sin
volver a pasar por bcrypt. Con texto plano, todo sigue como antes.
"""

from unittest.mock import patch

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.password import Password

CLAVE = "V@l1dP@ss123!"
NUEVA = "N3w$ecureP@ss99"


def _usuario() -> User:
    return User.create(
        first_name="Ana", last_name="Lopez", email_str="ana@example.com", plain_password=CLAVE
    )


def test_create_with_a_ready_password_does_not_hash_again():
    """
    Given: Una contraseña ya calculada
    When: Se crea el usuario con ella
    Then: La usa tal cual: ningún bcrypt más, y verifica con la contraseña original
    """
    lista = Password.from_plain_text(CLAVE)

    with patch.object(Password, "_hash_password", side_effect=AssertionError("bcrypt")):
        user = User.create(
            first_name="Ana", last_name="Lopez", email_str="ana@example.com", plain_password=lista
        )

    assert user.password is lista
    assert user.verify_password(CLAVE)


def test_change_password_with_a_ready_password_does_not_hash_again():
    """
    Given: Un usuario y una contraseña nueva ya calculada
    When: La cambia
    Then: Queda la nueva, sin bcrypt dentro del dominio, y con su evento
    """
    user = _usuario()
    nueva = Password.from_plain_text(NUEVA)

    with patch.object(Password, "_hash_password", side_effect=AssertionError("bcrypt")):
        user.change_password(nueva)

    assert user.password is nueva
    assert user.verify_password(NUEVA)
    assert any(type(e).__name__ == "UserPasswordChangedEvent" for e in user.get_domain_events())


def test_reset_password_with_a_ready_password_checks_the_token_first():
    """
    Given: Un usuario con un token de restablecer
    When: Restablece con una contraseña ya calculada; y antes, con un token malo
    Then: Con el malo, error y la contraseña de antes; con el bueno, la nueva sin bcrypt
    """
    user = _usuario()
    token = user.generate_password_reset_token()
    nueva = Password.from_plain_text(NUEVA)

    with pytest.raises(Exception):
        user.reset_password("otro-token", nueva)
    assert user.verify_password(CLAVE)

    with patch.object(Password, "_hash_password", side_effect=AssertionError("bcrypt")):
        user.reset_password(token, nueva)

    assert user.password is nueva
    assert user.password_reset_token is None
