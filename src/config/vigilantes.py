"""
Las tareas que corren solas dentro de la API, montadas con sus piezas reales.

Vive aquí, en la raíz de composición, porque cruza módulos: el refresco de
hándicaps de las 3:00 (BE #502) usa la competición, los usuarios y los campos.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.competition.application.use_cases.refrescar_handicaps_del_dia_use_case import (
    RefrescarHandicapsDelDiaUseCase,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.competition.infrastructure.services.competition_timezone_from_course import (
    CompetitionTimezoneFromCourse,
)
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)


def vuelta_con_la_base_de_datos(
    fabrica_de_sesiones: async_sessionmaker[AsyncSession],
    handicap_service: HandicapService,
) -> Callable[[], Awaitable[int]]:
    """
    Una vuelta real: abre su propia sesión, que comparten la competición, los
    usuarios y los campos, y la cierra al acabar.
    """

    async def vuelta() -> int:
        async with fabrica_de_sesiones() as sesion:
            competiciones = SQLAlchemyCompetitionUnitOfWork(sesion)
            usuarios = SQLAlchemyUserRepository(sesion)
            caso = RefrescarHandicapsDelDiaUseCase(
                unidad_de_trabajo=lambda: (competiciones, usuarios),
                handicap_service=handicap_service,
                timezone=CompetitionTimezoneFromCourse(
                    GolfCourseRepository(sesion), competiciones.competitions
                ),
                reloj=lambda: datetime.now(UTC),
                esperar=asyncio.sleep,
            )
            return await caso.execute()

    return vuelta
