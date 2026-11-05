"""
La limpieza de dispositivos y refrescos viejos, cada hora (BE #737).

Como el cierre de partidas rápidas: una tarea del propio proceso de la API con
candado de Postgres, para que con varios procesos solo limpie uno. Se arranca en
el `lifespan` en PRO y en el Kind; en los tests nunca.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.candado_de_postgres import con_candado
from src.modules.user.application.use_cases.purge_stale_sessions_use_case import (
    PurgeStaleSessionsUseCase,
    SesionesBorradas,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)

logger = logging.getLogger(__name__)

# Su propio candado: distinto del del cierre (2310_2026) y del vigilante de hándicaps
CANDADO_DE_LA_LIMPIEZA = 511_2026
INTERVALO_SEGUNDOS = 60 * 60


class LimpiezaDeSesiones:
    """Una vuelta por hora: borra los dispositivos y refrescos viejos."""

    def __init__(
        self,
        fabrica: async_sessionmaker[AsyncSession],
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
        reloj: Callable[[], datetime] = datetime.now,
    ):
        self._fabrica = fabrica
        self._esperar = esperar
        self._reloj = reloj

    async def vigilar(self) -> None:
        """Hasta que la app se apague. Una vuelta que falla no para las siguientes."""
        while True:
            try:
                resumen = await self.vuelta()
                if resumen and (resumen.dispositivos or resumen.tokens):
                    logger.info(
                        "Old sessions cleaned: %s devices, %s refresh tokens",
                        resumen.dispositivos,
                        resumen.tokens,
                    )
            except Exception:
                logger.exception("Session cleanup failed; retrying next hour")
            await self._esperar(INTERVALO_SEGUNDOS)

    async def vuelta(self) -> SesionesBorradas | None:
        """Una vuelta, o None si otro proceso tiene el candado."""
        return await con_candado(self._fabrica.kw["bind"], CANDADO_DE_LA_LIMPIEZA, self._limpia)

    async def _limpia(self) -> SesionesBorradas:
        async with self._fabrica() as sesion:
            return await PurgeStaleSessionsUseCase(SQLAlchemyUnitOfWork(sesion)).execute(
                self._reloj()
            )
