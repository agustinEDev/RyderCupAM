"""
El usuario acepta una contraseña ya calculada (BE #283, 7 nov 2026).

El bcrypt se calcula fuera de la transacción y se le entrega después al dominio: con un
`Password` ya hecho por `from_plain_text`, `change_password` y `reset_password` lo usan tal
cual, sin volver a pasar por bcrypt. Con texto plano, todo sigue como antes.
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


def test_a_password_built_from_any_hash_is_refused():
    """
    Given: Un Password construido a mano con un hash cualquiera (sin pasar por la política)
    When: Se le da al usuario
    Then: Lo rechaza: solo vale el que sale de from_plain_text (revisores del bloque 2)
    """
    user = _usuario()
    cualquiera = Password(Password.from_plain_text(NUEVA).hashed_value)

    with pytest.raises(ValueError, match="from_plain_text"):
        user.change_password(cualquiera)
    assert user.verify_password(CLAVE)


def test_the_policy_can_be_checked_without_hashing():
    """
    Given: Una contraseña buena y una que no cumple la política
    When: Se comprueba la política
    Then: La buena pasa y la mala da su error, sin calcular ningún bcrypt
    """
    from src.modules.user.domain.value_objects.password import InvalidPasswordError

    with patch.object(Password, "_hash_password", side_effect=AssertionError("bcrypt")):
        Password.comprueba_la_politica(NUEVA)
        with pytest.raises(InvalidPasswordError):
            Password.comprueba_la_politica("solamenteletras")


def test_two_equal_hashes_are_equal_whatever_their_origin():
    """
    Given: Un Password recién hecho y otro construido con su mismo hash (como al leer de la BD)
    When: Se comparan
    Then: Son iguales: la marca no cuenta (el login compara así la contraseña comprobada)
    """
    nueva = Password.from_plain_text(NUEVA)

    assert Password(nueva.hashed_value) == nueva


def test_the_mark_cannot_be_set_from_outside():
    """
    Given: Un hash cualquiera
    When: Se intenta construir un Password con la marca, o copiarlo poniéndola
    Then: No se puede: la marca solo la pone from_plain_text (/code-review)
    """
    import dataclasses

    with pytest.raises(TypeError):
        Password("hash", de_texto_plano=True)
    with pytest.raises((TypeError, ValueError)):
        dataclasses.replace(Password("hash"), de_texto_plano=True)


def test_the_password_maps_to_a_single_column():
    """
    Given: El mapeo de User (composite de una columna para la contraseña)
    When: SQLAlchemy saca los valores de un Password
    Then: Uno solo, el hash: la marca no se cuela en la BD (revisor de arquitectura)
    """
    from sqlalchemy import inspect

    from src.config.mappers import start_all_mappers

    start_all_mappers()
    contrasena = Password.from_plain_text(NUEVA)

    valores = inspect(User).attrs["_password"]._composite_values_from_instance(contrasena)

    assert valores == (contrasena.hashed_value,)
