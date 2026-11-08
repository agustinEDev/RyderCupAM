"""
Qué violación de la base de datos es «ya registrado» en el alta (R1, 7 nov 2026).

Solo la restricción única del correo de users; cualquier otra sigue como hoy (500), para
no esconder un fallo distinto bajo «ya registrado».
"""

import pytest
from sqlalchemy.exc import IntegrityError

from src.modules.user.infrastructure.api.v1.auth_routes import _es_el_correo_repetido


class _AsyncpgError(Exception):
    def __init__(self, constraint_name):
        super().__init__("violates unique constraint")
        self.constraint_name = constraint_name


def _error(nombre=None, texto="duplicate key"):
    original = Exception(texto)
    if nombre is not None:
        original.__cause__ = _AsyncpgError(nombre)
    return IntegrityError("INSERT", {}, original)


@pytest.mark.parametrize(
    ("error", "es"),
    [
        (_error("users_email_key"), True),
        (_error("terms_acceptances_user_id_fkey"), False),
        (_error("ix_users_alias_lower"), False),
        (_error(texto='duplicate key value violates unique constraint "users_email_key"'), True),
        (_error(texto="otra cosa"), False),
    ],
)
def test_only_the_users_email_constraint_is_already_registered(error, es):
    """
    Given: Una violación de la base de datos al guardar el alta
    When: Se decide si es el correo repetido
    Then: Solo si es users_email_key (por su nombre o, sin él, por su texto)
    """
    assert _es_el_correo_repetido(error) is es
