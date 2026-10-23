"""
El cierre de las partidas rápidas que nadie termina, cada hora (Agustín, 23 oct 2026).

Vive aquí, en la raíz de composición, porque cruza módulos: cierra en
`quick_match` y publica en Actividad (`social`), como al finalizar a mano.

Una tarea del propio proceso de la API, como el vigilante de hándicaps, con su
candado de Postgres: con varios procesos, solo uno cierra. Se arranca en el
`lifespan` en PRO y en el Kind; en los tests (`TESTING=true`) nunca.

Cada vuelta usa dos sesiones: la del cierre y la de Actividad, que publica
después de guardado el cierre y no debe deshacerlo si falla (ver
`get_activity_db_session`).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.candado_de_postgres import con_candado
from src.config.dependencies import (
    get_activity_units_of_work,
    get_publish_quick_match_result_use_case,
    get_publish_round_achievements_use_case,
    get_round_achievements_publisher,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.quick_match.application.use_cases.close_expired_quick_matches_use_case import (
    ClosedQuickMatches,
    CloseExpiredQuickMatchesUseCase,
)
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_unit_of_work import (
    SQLAlchemyQuickMatchUnitOfWork,
)

logger = logging.getLogger(__name__)

# El candado del cierre: un número cualquiera, siempre el mismo y distinto del
# del vigilante de hándicaps
CANDADO_DEL_CIERRE = 2310_2026
INTERVALO_SEGUNDOS = 60 * 60


def cierre_activado(entorno: Mapping[str, str]) -> bool:
    """Siempre, salvo en los tests."""
    return entorno.get("TESTING", "").lower() != "true"


class CierreDePartidasRapidas:
    """Una vuelta por hora: cierra las partidas rápidas pasadas de plazo."""

    def __init__(
        self,
        fabrica: async_sessionmaker[AsyncSession],
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
        reloj: Callable[[], datetime] | None = None,
    ):
        self._fabrica = fabrica
        self._esperar = esperar
        # Sin reloj, el del caso de uso: ahora en UTC
        self._reloj = reloj

    async def vigilar(self) -> None:
        """Hasta que la app se apague (se cancela la tarea). Una vuelta que falla no para las siguientes."""
        while True:
            try:
                resumen = await self.vuelta()
                if resumen and (resumen.completed or resumen.cancelled):
                    logger.info(
                        "Quick matches closed on their own: %s completed (%s published), "
                        "%s cancelled",
                        resumen.completed,
                        resumen.published,
                        resumen.cancelled,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("A pass of the quick match closing failed")
            await self._esperar(INTERVALO_SEGUNDOS)

    async def vuelta(self) -> ClosedQuickMatches | None:
        """Una vuelta, o None si otro proceso tiene el candado."""
        return await con_candado(self._fabrica.kw["bind"], CANDADO_DEL_CIERRE, self._cierra)

    async def _cierra(self) -> ClosedQuickMatches:
        async with self._fabrica() as sesion, self._fabrica() as sesion_de_actividad:
            uows = get_activity_units_of_work(sesion_de_actividad)
            publicador = get_round_achievements_publisher(
                get_publish_round_achievements_use_case(uows),
                get_publish_quick_match_result_use_case(uows),
            )
            relojes = {"reloj": self._reloj} if self._reloj else {}
            return await CloseExpiredQuickMatchesUseCase(
                SQLAlchemyQuickMatchUnitOfWork(sesion),
                SQLAlchemyGolfCourseUnitOfWork(sesion),
                publicador,
                **relojes,
            ).execute()
