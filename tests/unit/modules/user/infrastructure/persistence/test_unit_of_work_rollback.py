"""
Un guardado que falla al salir de la unidad de trabajo la deja usable (CodeRabbit en
#752): antes, si el commit fallaba (una restricción única), nadie hacía rollback y la
sesión quedaba inservible para lo siguiente de la misma petición.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)


@pytest.mark.asyncio
async def test_a_failed_commit_is_rolled_back_and_raised():
    """
    Given: un commit que falla
    When: sale de la unidad de trabajo
    Then: se hace rollback y el error sube
    """
    sesion = MagicMock()
    sesion.commit = AsyncMock(side_effect=RuntimeError("duplicate key"))
    sesion.rollback = AsyncMock()
    uow = SQLAlchemyUnitOfWork(sesion)

    with pytest.raises(RuntimeError):
        async with uow:
            pass

    sesion.rollback.assert_awaited_once()


def _violacion(indice: str):
    """Un IntegrityError como el de Postgres al chocar con ese índice."""
    from sqlalchemy.exc import IntegrityError

    return IntegrityError(
        "UPDATE users ...",
        {},
        Exception(f'duplicate key value violates unique constraint "{indice}"'),
    )


@pytest.mark.asyncio
async def test_the_alias_index_violation_becomes_alias_already_taken():
    """
    Given: un commit que choca con el índice único del alias (otra petición se
           llevó el mismo alias entre la comprobación y el commit)
    When: sale de la unidad de trabajo
    Then: sale AliasTakenConcurrentlyError (un AliasAlreadyTakenError) del dominio, con rollback hecho; el caso de
          uso no tiene que conocer SQLAlchemy ni el nombre del índice (auditoría
          de arquitectura del 9 nov 2026, B1)
    """
    from src.modules.user.domain.errors.user_errors import AliasTakenConcurrentlyError

    sesion = MagicMock()
    sesion.commit = AsyncMock(side_effect=_violacion("ix_users_alias_lower"))
    sesion.rollback = AsyncMock()
    uow = SQLAlchemyUnitOfWork(sesion)

    with pytest.raises(AliasTakenConcurrentlyError):
        async with uow:
            pass

    sesion.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_alias_index_violation_on_flush_becomes_alias_already_taken():
    """
    Given: un flush que choca con el índice único del alias
    When: se hace el flush
    Then: sale AliasTakenConcurrentlyError (un AliasAlreadyTakenError), igual que en el commit
    """
    from src.modules.user.domain.errors.user_errors import AliasTakenConcurrentlyError

    sesion = MagicMock()
    sesion.flush = AsyncMock(side_effect=_violacion("ix_users_alias_lower"))
    sesion.rollback = AsyncMock()
    uow = SQLAlchemyUnitOfWork(sesion)

    with pytest.raises(AliasTakenConcurrentlyError):
        await uow.flush()


@pytest.mark.asyncio
async def test_other_integrity_errors_are_not_translated():
    """
    Given: un commit que choca con OTRA restricción (el correo)
    When: sale de la unidad de trabajo
    Then: sube el IntegrityError tal cual: llamarlo «alias cogido» mandaría al
          usuario a cambiar lo que no falla
    """
    from sqlalchemy.exc import IntegrityError

    sesion = MagicMock()
    sesion.commit = AsyncMock(side_effect=_violacion("users_email_key"))
    sesion.rollback = AsyncMock()
    uow = SQLAlchemyUnitOfWork(sesion)

    with pytest.raises(IntegrityError):
        async with uow:
            pass


@pytest.mark.asyncio
async def test_an_alias_violation_from_autoflush_inside_the_block_is_translated():
    """
    Given: una consulta dentro del bloque que dispara el autoflush y choca con el
           índice del alias (no pasa por commit ni por flush de la unidad de trabajo)
    When: el error sale del bloque
    Then: sale AliasTakenConcurrentlyError (un AliasAlreadyTakenError), con rollback: una carrera del alias es un
          409, nunca un 500
    """
    from src.modules.user.domain.errors.user_errors import AliasTakenConcurrentlyError

    sesion = MagicMock()
    sesion.rollback = AsyncMock()
    uow = SQLAlchemyUnitOfWork(sesion)

    with pytest.raises(AliasTakenConcurrentlyError):
        async with uow:
            raise _violacion("ix_users_alias_lower")

    sesion.rollback.assert_awaited_once()
