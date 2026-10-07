"""
La actualización de hándicaps con la RFEG en segundo plano, con sus piezas reales (#251).

Vive aquí, en la raíz de composición, porque cruza módulos: usa la competición,
los usuarios, la RFEG y el correo.

Al cerrar las inscripciones, la petición guarda una actualización y la lanza
aquí, en una tarea del propio proceso de la API: la respuesta no espera a la
RFEG. Si el servidor se reinicia a mitad, la tarea muere y la actualización
se queda en curso: detectarlo y avisar llega con el botón del organizador.

**Solo en producción**: apagado por defecto y encendido con
`HANDICAP_REFRESH_ENABLED=true`, que solo se pone en Render. Así el Kind y el
entorno local no preguntan a la RFEG real por los usuarios de prueba (ni mandan
correos de aviso). En los tests (`TESTING=true`) nunca, aunque se encienda.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.competition.application.ports.handicap_update_email_service_interface import (
    IHandicapUpdateEmailService,
)
from src.modules.competition.application.ports.lanzador_de_actualizaciones import (
    LanzadorDeActualizaciones,
)
from src.modules.competition.application.use_cases.refrescar_handicaps_use_case import (
    Herramientas,
    RefrescarHandicapsUseCase,
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

logger = logging.getLogger(__name__)

_ENCENDIDO = {"true", "1", "yes", "on"}


def refresco_activado(entorno: Mapping[str, str]) -> bool:
    """Solo con `HANDICAP_REFRESH_ENABLED` encendido, y nunca en los tests."""
    if entorno.get("TESTING", "").lower() == "true":
        return False
    return entorno.get("HANDICAP_REFRESH_ENABLED", "").strip().lower() in _ENCENDIDO


class LanzadorEnSegundoPlano(LanzadorDeActualizaciones):
    """Lanza cada pasada en una tarea del proceso, con sesiones propias."""

    def __init__(
        self,
        fabrica_de_sesiones: async_sessionmaker[AsyncSession],
        handicap_service: HandicapService,
        avisos: IHandicapUpdateEmailService,
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._fabrica = fabrica_de_sesiones
        self._handicap_service = handicap_service
        self._avisos = avisos
        self._esperar = esperar
        # Referencias fuertes: una tarea sin ellas puede desaparecer a medias
        self._tareas: set[asyncio.Task[int | None]] = set()

    def lanzar(self, update_id: uuid.UUID) -> None:
        tarea = asyncio.create_task(self.pasada(update_id))
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    async def pasada(self, update_id: uuid.UUID) -> int | None:
        """Una pasada entera; un fallo se registra y no sale de aquí."""
        try:
            return await RefrescarHandicapsUseCase(
                herramientas=self._herramientas,
                handicap_service=self._handicap_service,
                avisos=self._avisos,
                reloj=lambda: datetime.now(UTC),
                esperar=self._esperar,
            ).execute(update_id)
        except Exception:
            logger.exception("Falló la actualización de hándicaps %s", update_id)
            return None

    async def esperar_a_todas(self) -> None:
        """Hasta que acaben las que estén en marcha (para los tests)."""
        await asyncio.gather(*self._tareas, return_exceptions=True)

    @asynccontextmanager
    async def _herramientas(self) -> AsyncIterator[Herramientas]:
        """Una sesión propia, que comparten la competición, los usuarios y los campos."""
        async with self._fabrica() as sesion:
            competiciones = SQLAlchemyCompetitionUnitOfWork(sesion)
            yield Herramientas(
                competiciones=competiciones,
                usuarios=SQLAlchemyUserRepository(sesion),
                zonas=CompetitionTimezoneFromCourse(
                    GolfCourseRepository(sesion), competiciones.competitions
                ),
            )
