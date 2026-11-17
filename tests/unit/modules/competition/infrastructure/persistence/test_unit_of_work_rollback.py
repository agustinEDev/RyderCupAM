"""
Un guardado que falla al salir de la unidad de trabajo de competición la deja usable, como
la de usuarios (CodeRabbit en #752): sin rollback, la sesión quedaba inservible para lo
siguiente de la misma petición. Con los commits explícitos de partidas quitados (re-auditoría
F-11), el commit de la salida es el único.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)


@pytest.mark.asyncio
async def test_salir_commit_que_falla_hace_rollback_y_sube_el_error():
    """
    Given: un commit que falla
    When: sale de la unidad de trabajo
    Then: se hace rollback y el error sube
    """
    sesion = MagicMock()
    sesion.commit = AsyncMock(side_effect=RuntimeError("duplicate key"))
    sesion.rollback = AsyncMock()
    uow = SQLAlchemyCompetitionUnitOfWork(sesion)

    with pytest.raises(RuntimeError):
        async with uow:
            pass

    sesion.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_salir_sin_fallos_hace_commit_sin_rollback():
    """
    Given: un bloque sin errores
    When: sale de la unidad de trabajo
    Then: commit y ningún rollback
    """
    sesion = MagicMock()
    sesion.commit = AsyncMock()
    sesion.rollback = AsyncMock()
    uow = SQLAlchemyCompetitionUnitOfWork(sesion)

    async with uow:
        pass

    sesion.commit.assert_awaited_once()
    sesion.rollback.assert_not_awaited()
