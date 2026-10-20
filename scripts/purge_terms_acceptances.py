"""
Purga el historial de aceptaciones de los Términos de las cuentas borradas.

POR QUE
-------
La prueba de que alguien aceptó los Términos (tabla `terms_acceptances`) se
conserva después de borrar su cuenta, pero no para siempre: decisión de
Agustín del 20 oct 2026, TERMS_ACCEPTANCE_RETENTION_YEARS (3) años naturales
desde el borrado (ver src/modules/user/domain/services/terms_of_service.py).
Este script borra las filas que ya han cumplido ese plazo. Las de cuentas que
siguen existiendo no se tocan nunca.

POR QUE UN SCRIPT Y NO UNA TAREA PERIODICA
------------------------------------------
El único bucle periódico del backend es el vigilante de hándicaps
(src/config/refresco_de_handicaps.py): es del módulo de competición y solo se
enciende con HANDICAP_REFRESH_ENABLED. Colgar de él una purga del módulo de
usuarios ataría dos cosas que no tienen que ver, y la purga dependería de un
interruptor de la RFEG. Con un plazo de años, no hace falta precisión: basta
con pasarlo de vez en cuando (por ejemplo, en cada release). Las primeras filas
purgables aparecerán en 2029 como pronto.

USO
---
    source .venv/bin/activate
    PYTHONPATH=. python scripts/purge_terms_acceptances.py

Es idempotente: pasarlo dos veces seguidas no borra nada la segunda.
"""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.mappers import start_all_mappers
from src.modules.user.application.dto.user_dto import (
    PurgeTermsAcceptancesRequestDTO,
    PurgeTermsAcceptancesResponseDTO,
)
from src.modules.user.application.use_cases.purge_terms_acceptances_use_case import (
    PurgeTermsAcceptancesUseCase,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)


async def purgar(
    sesiones: Callable[[], AbstractAsyncContextManager[AsyncSession]], ahora: datetime
) -> PurgeTermsAcceptancesResponseDTO:
    """
    Pasa la purga con una sesión de esa fábrica y `ahora` como referencia.

    Args:
        sesiones: Fábrica de sesiones (la de la app, o la de un test)
        ahora: Instante de referencia, en UTC
    """
    async with sesiones() as session:
        return await PurgeTermsAcceptancesUseCase(SQLAlchemyUnitOfWork(session)).execute(
            PurgeTermsAcceptancesRequestDTO(now=ahora)
        )


async def main() -> int:
    """Purga contra la base de datos de DATABASE_URL y dice cuántas filas borró."""
    from src.config.database import async_session_maker  # noqa: PLC0415

    start_all_mappers()
    respuesta = await purgar(async_session_maker, datetime.now(UTC))
    print(
        f"Historial de Términos: {respuesta.deleted} fila(s) de cuentas borradas "
        f"antes del {respuesta.cutoff.isoformat()} purgadas."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
