"""
La traducción del alias repetido, contra Postgres de verdad (CodeRabbit en #773).

Los tests unitarios de la unidad de trabajo le dan un error de driver simulado; este
comprueba que el mensaje real de Postgres nombra el índice `ix_users_alias_lower`
y que la unidad de trabajo lo traduce al error del dominio, con rollback.
"""

import pytest

from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import AliasTakenConcurrentlyError
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)

pytestmark = pytest.mark.integration


def _usuario(correo: str) -> User:
    """Un usuario con el alias que se van a disputar."""
    usuario = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=correo,
        plain_password="ValidPassword123!",
    )
    usuario.update_profile(alias="Chuchi")
    return usuario


async def test_a_duplicate_alias_comes_out_as_the_domain_error(db_session):
    """
    Given: un usuario guardado con el alias «Chuchi»
    When: otro se guarda con «chuchi» por la unidad de trabajo (la carrera que la
          comprobación previa del caso de uso no puede ver)
    Then: sale AliasTakenConcurrentlyError, y la sesión queda usable tras el rollback
    """
    uow = SQLAlchemyUnitOfWork(db_session)
    async with uow:
        await uow.users.save(_usuario("alias.pg.uno@example.com"))

    segundo = _usuario("alias.pg.dos@example.com")
    segundo.update_profile(alias="chuchi")

    with pytest.raises(AliasTakenConcurrentlyError):
        async with uow:
            await uow.users.save(segundo)

    assert uow.is_active()
    async with uow:
        assert await uow.users.find_by_alias("Chuchi") is not None
