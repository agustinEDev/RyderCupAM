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
    sesion = MagicMock()
    sesion.commit = AsyncMock(side_effect=RuntimeError("duplicate key"))
    sesion.rollback = AsyncMock()
    uow = SQLAlchemyUnitOfWork(sesion)

    with pytest.raises(RuntimeError):
        async with uow:
            pass

    sesion.rollback.assert_awaited_once()
