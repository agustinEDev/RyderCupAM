"""
Un guardado que falla al salir de la unidad de trabajo de social la deja usable, como la de
usuarios (#752) y la de competición: sin rollback, la sesión quedaba inservible para lo
siguiente de la misma petición.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.social.infrastructure.persistence.sqlalchemy.social_unit_of_work import (
    SQLAlchemySocialUnitOfWork,
)


@pytest.mark.asyncio
async def test_salir_commit_que_falla_hace_rollback_y_sube_el_error():
    """
    Given: un commit que falla
    When: sale de la unidad de trabajo
    Then: se hace rollback y sube el error del commit
    """
    sesion = MagicMock()
    sesion.commit = AsyncMock(side_effect=RuntimeError("duplicate key"))
    sesion.flush = AsyncMock()
    sesion.rollback = AsyncMock()
    uow = SQLAlchemySocialUnitOfWork(sesion)

    with pytest.raises(RuntimeError, match="duplicate key"):
        async with uow:
            pass

    sesion.rollback.assert_awaited_once()
