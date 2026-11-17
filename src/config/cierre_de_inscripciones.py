"""
El cierre de las inscripciones a las 12:00 del día anterior al torneo, cada hora
(decidido el 15 nov 2026).

Vive aquí, en la raíz de composición, porque cruza módulos: cierra en
`competition`, mira la zona del campo en `golf_course`, el hándicap en `user` y
avisa en Actividad (`social`), como al cerrar a mano.

Una tarea del propio proceso de la API, como el cierre de las partidas rápidas,
con su candado de Postgres: con varios procesos, solo uno cierra. Se arranca en
el `lifespan` en PRO y en el Kind; en los tests (`TESTING=true`) nunca.

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
    get_competition_activity_publisher,
    get_lanzador_de_actualizaciones,
    get_publish_competition_notices_use_case,
    get_publish_round_achievements_use_case,
    get_publish_tournament_achievements_use_case,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    PlazoDeInscripcion,
)
from src.modules.competition.application.use_cases.close_enrollments_past_deadline_use_case import (
    ClosedByDeadline,
    CloseEnrollmentsPastDeadlineUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.competition.infrastructure.services.competition_timezone_from_course import (
    CompetitionTimezoneFromCourse,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.shared.domain.services.instante_utc import ahora_en_utc

logger = logging.getLogger(__name__)

# El candado del cierre: un número cualquiera, siempre el mismo y distinto de
# los del vigilante de hándicaps y del cierre de las partidas rápidas
CANDADO_DEL_CIERRE_DE_INSCRIPCIONES = 1511_2026
INTERVALO_SEGUNDOS = 60 * 60


def cierre_de_inscripciones_activado(entorno: Mapping[str, str]) -> bool:
    """Siempre, salvo en los tests."""
    return entorno.get("TESTING", "").lower() != "true"


class CierreDeInscripciones:
    """Una vuelta por hora: cierra las inscripciones a las que les pasó el plazo."""

    def __init__(
        self,
        fabrica: async_sessionmaker[AsyncSession],
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
        reloj: Callable[[], datetime] = ahora_en_utc,
    ):
        self._fabrica = fabrica
        self._esperar = esperar
        self._reloj = reloj
        # Las que ya fallaron con otro error en este proceso: su traza, una vez (F4)
        self._fallos: set[CompetitionId] = set()

    async def vigilar(self) -> None:
        """Hasta que la app se apague (se cancela la tarea). Una vuelta que falla no para las siguientes."""
        while True:
            try:
                resumen = await self.vuelta()
                if resumen and (resumen.closed or resumen.blocked or resumen.failed):
                    logger.info(
                        "Enrollments closed by their deadline: %s closed, %s blocked "
                        "(%s notified), %s failed",
                        resumen.closed,
                        resumen.blocked,
                        resumen.notified,
                        resumen.failed,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("A pass of the enrollment closing failed")
            await self._esperar(INTERVALO_SEGUNDOS)

    async def vuelta(self) -> ClosedByDeadline | None:
        """Una vuelta, o None si otro proceso tiene el candado."""
        return await con_candado(
            self._fabrica.kw["bind"], CANDADO_DEL_CIERRE_DE_INSCRIPCIONES, self._cierra
        )

    async def _cierra(self) -> ClosedByDeadline:
        async with self._fabrica() as sesion, self._fabrica() as sesion_de_actividad:
            uows = get_activity_units_of_work(sesion_de_actividad)
            actividad = get_competition_activity_publisher(
                notices=get_publish_competition_notices_use_case(uows),
                uows=uows,
                achievements=get_publish_tournament_achievements_use_case(uows),
                round_achievements=get_publish_round_achievements_use_case(uows),
            )
            uow = SQLAlchemyCompetitionUnitOfWork(sesion)
            plazo = PlazoDeInscripcion(
                CompetitionTimezoneFromCourse(
                    SQLAlchemyGolfCourseUnitOfWork(sesion).golf_courses, uow.competitions
                ),
                reloj=self._reloj,
            )
            cerrar = CloseEnrollmentsUseCase(
                uow,
                SQLAlchemyUnitOfWork(sesion).users,
                get_lanzador_de_actualizaciones(),
                actividad=actividad,
                plazo=plazo,
            )
            return await CloseEnrollmentsPastDeadlineUseCase(
                uow, cerrar, plazo, actividad=actividad, fallos_conocidos=self._fallos
            ).execute()
