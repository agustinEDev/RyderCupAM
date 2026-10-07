"""
Las tareas que corren solas dentro de la API, montadas con sus piezas reales.

Vive aquí, en la raíz de composición, porque cruza módulos: el refresco de
hándicaps de las 3:00 (BE #502) usa la competición, los usuarios y los campos.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.competition.application.use_cases.refrescar_handicaps_del_dia_use_case import (
    Herramientas,
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

# El candado de Postgres de la vuelta: un número cualquiera, siempre el mismo
CANDADO_DEL_REFRESCO = 502_0300


def vuelta_con_la_base_de_datos(
    fabrica_de_sesiones: async_sessionmaker[AsyncSession],
    handicap_service: HandicapService,
) -> Callable[[], Awaitable[int | None]]:
    """
    Una vuelta real del refresco de las 3:00.

    Pide un candado de Postgres antes de empezar: con dos procesos a la vez
    —un despliegue justo a las 3:00—, el segundo se salta la vuelta en vez de
    preguntar lo mismo a la RFEG. El candado va en una conexión propia, sin
    transacción abierta, y se suelta al acabar; si el proceso muere, Postgres
    lo suelta solo al cerrarse la conexión.

    Cada parte de la vuelta pide herramientas nuevas: una sesión propia, que
    comparten la competición, los usuarios y los campos, y que se cierra al
    acabar esa parte.
    """
    motor = fabrica_de_sesiones.kw["bind"]

    @asynccontextmanager
    async def herramientas() -> AsyncIterator[Herramientas]:
        async with fabrica_de_sesiones() as sesion:
            competiciones = SQLAlchemyCompetitionUnitOfWork(sesion)
            yield Herramientas(
                competiciones=competiciones,
                usuarios=SQLAlchemyUserRepository(sesion),
                zonas=CompetitionTimezoneFromCourse(
                    GolfCourseRepository(sesion), competiciones.competitions
                ),
            )

    async def vuelta() -> int | None:
        async with motor.connect() as candado:
            cogido = await candado.scalar(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": CANDADO_DEL_REFRESCO}
            )
            # El candado es de la conexión, no de la transacción: se cierra
            # para no dejarla abierta toda la vuelta
            await candado.commit()
            if not cogido:
                return None
            try:
                return await RefrescarHandicapsDelDiaUseCase(
                    herramientas=herramientas,
                    handicap_service=handicap_service,
                    reloj=lambda: datetime.now(UTC),
                    esperar=asyncio.sleep,
                ).execute()
            finally:
                await candado.scalar(
                    text("SELECT pg_advisory_unlock(:k)"), {"k": CANDADO_DEL_REFRESCO}
                )
                await candado.commit()

    return vuelta
