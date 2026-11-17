"""
La actualización de hándicaps con la RFEG en segundo plano, con sus piezas reales (#251).

Vive aquí, en la raíz de composición, porque cruza módulos: usa la competición,
los usuarios, la RFEG y el correo.

Al cerrar las inscripciones, la petición guarda una actualización y la lanza
aquí, en una tarea del propio proceso de la API: la respuesta no espera a la
RFEG. Si el servidor se reinicia a mitad, la tarea muere y la actualización
se queda en curso: detectarlo y avisar llega con el botón del organizador.

Al terminar, la pasada avisa también en Actividad (15 nov 2026), con una sesión
propia para Actividad, como el cierre de las partidas rápidas: lo que publica
no debe deshacer lo guardado si falla. Se monta solo al avisar, con la pasada
ya hecha (T1): si montarla o cerrarla falla, la pasada no se entera.

El vigilante, una vuelta por minuto en el mismo proceso, solo lanza las
actualizaciones programadas y recupera las que un reinicio dejó en curso.

**Solo en producción**: apagado por defecto y encendido con
`HANDICAP_REFRESH_ENABLED=true`, que solo se pone en Render. Así el Kind y el
entorno local no preguntan a la RFEG real por los usuarios de prueba (ni mandan
correos de aviso). En los tests (`TESTING=true`) nunca, aunque se encienda.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.candado_de_postgres import con_candado
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.handicap_update_email_service_interface import (
    IHandicapUpdateEmailService,
)
from src.modules.competition.application.ports.lanzador_de_actualizaciones import (
    LanzadorDeActualizaciones,
)
from src.modules.competition.application.use_cases.handicap_de_la_rfeg_del_perfil_use_case import (
    HandicapDeLaRfegDelPerfilUseCase,
)
from src.modules.competition.application.use_cases.refrescar_handicaps_use_case import (
    Herramientas,
    RefrescarHandicapsUseCase,
)
from src.modules.competition.application.use_cases.vigilar_actualizaciones_use_case import (
    VigilarActualizacionesUseCase,
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
from src.modules.user.application.ports.handicap_de_la_rfeg_port import (
    IHandicapEncontradoEnLaRfeg,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)
from src.shared.domain.services.instante_utc import ahora_en_utc

logger = logging.getLogger(__name__)

_ENCENDIDO = {"true", "1", "yes", "on"}

# Monta Actividad sobre una sesión: la da la composición de dependencias, que
# importa este módulo (pasarla evita el ciclo)
ConstruirActividad = Callable[[AsyncSession], CompetitionActivityPublisherInterface]


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
        actividad: ConstruirActividad | None = None,
    ):
        self.fabrica = fabrica_de_sesiones
        self._handicap_service = handicap_service
        self.avisos = avisos
        self._esperar = esperar
        self._actividad = actividad
        # Referencias fuertes: una tarea sin ellas puede desaparecer a medias
        self._tareas: set[asyncio.Task[int | None]] = set()

    def tareas_en_marcha(self) -> list[asyncio.Task[int | None]]:
        """Las actualizaciones que siguen corriendo, para esperarlas al apagar."""
        return [t for t in self._tareas if not t.done()]

    def lanzar(self, update_id: uuid.UUID) -> None:
        self._en_segundo_plano(self.pasada(update_id))

    def del_perfil(self, user_id: UserId, handicap: Decimal) -> None:
        """
        La RFEG dio su hándicap desde el perfil: sus competiciones, en segundo
        plano (R6). Quien lo pidió no espera a los bloqueos de las competiciones.
        """
        self._en_segundo_plano(self._del_perfil(user_id, handicap))

    def _en_segundo_plano(self, trabajo: Coroutine[Any, Any, int | None]) -> None:
        tarea = asyncio.create_task(trabajo)
        self._tareas.add(tarea)
        tarea.add_done_callback(self._tareas.discard)

    async def _del_perfil(self, user_id: UserId, handicap: Decimal) -> None:
        """Lo del perfil en sus competiciones; un fallo se registra una vez y no sale (R8)."""
        try:
            await HandicapDeLaRfegDelPerfilUseCase(
                herramientas=self.herramientas,
                reloj=ahora_en_utc,
                actividad=None if self._actividad is None else self._actividad_en_su_sesion,
            ).execute(user_id, handicap)
        except Exception:
            logger.exception("Could not pass the RFEG handicap of %s to its competitions", user_id)

    async def pasada(self, update_id: uuid.UUID) -> int | None:
        """Una pasada entera; un fallo se registra y no sale de aquí."""
        try:
            return await RefrescarHandicapsUseCase(
                herramientas=self.herramientas,
                handicap_service=self._handicap_service,
                avisos=self.avisos,
                reloj=ahora_en_utc,
                esperar=self._esperar,
                # Se monta al avisar, con la pasada ya hecha: si falla, la pasada
                # no se entera (T1)
                actividad=None if self._actividad is None else self._actividad_en_su_sesion,
            ).execute(update_id)
        except Exception:
            logger.exception("Falló la actualización de hándicaps %s", update_id)
            return None

    def _actividad_en_su_sesion(
        self,
    ) -> AbstractAsyncContextManager[CompetitionActivityPublisherInterface]:
        """Actividad sobre su propia sesión, que se cierra al acabar de avisar."""
        if self._actividad is None:
            raise RuntimeError("Sin Actividad no hay nada que montar")
        return actividad_en(self.fabrica, self._actividad)

    async def esperar_a_todas(self) -> None:
        """Hasta que acaben las que estén en marcha (para los tests)."""
        await asyncio.gather(*self._tareas, return_exceptions=True)

    def herramientas(self) -> AbstractAsyncContextManager[Herramientas]:
        """Una sesión propia, que comparten la competición, los usuarios y los campos."""
        return herramientas_en(self.fabrica)


@asynccontextmanager
async def herramientas_en(
    fabrica: async_sessionmaker[AsyncSession],
) -> AsyncIterator[Herramientas]:
    """Competición, usuarios, campos y husos sobre una sesión propia de esa fábrica."""
    async with fabrica() as sesion:
        competiciones = SQLAlchemyCompetitionUnitOfWork(sesion)
        campos = GolfCourseRepository(sesion)
        yield Herramientas(
            competiciones=competiciones,
            usuarios=SQLAlchemyUserRepository(sesion),
            zonas=CompetitionTimezoneFromCourse(campos, competiciones.competitions),
            campos=campos,
        )


@asynccontextmanager
async def actividad_en(
    fabrica: async_sessionmaker[AsyncSession], construir: ConstruirActividad
) -> AsyncIterator[CompetitionActivityPublisherInterface]:
    """Actividad sobre una sesión propia de esa fábrica, que se cierra al salir."""
    async with fabrica() as sesion:
        yield construir(sesion)


class HandicapDeLaRfegEnLasCompeticiones(IHandicapEncontradoEnLaRfeg):
    """
    La RFEG dio el hándicap de un jugador desde su perfil o al entrar: sus
    competiciones cerradas lo apuntan y, en stroke play, corrigen su fijado (D1
    y D4, 16 nov 2026). Cruza módulos: por eso vive en la raíz de composición.

    Lo corre el lanzador del proceso en segundo plano (R6), con el mismo
    interruptor que las actualizaciones (R5): la respuesta no lo espera.
    """

    def __init__(self, lanzador: LanzadorEnSegundoPlano):
        self._lanzador = lanzador

    async def encontrado(self, user_id: UserId, handicap: float) -> None:
        self._lanzador.del_perfil(user_id, Decimal(str(handicap)))


# El candado de Postgres del vigilante: un número cualquiera, siempre el mismo
CANDADO_DEL_VIGILANTE = 251_0300
INTERVALO_SEGUNDOS = 60


class VigilanteDeActualizaciones:
    """
    Una vuelta por minuto: lanza las programadas y recupera las cortadas (#251).

    Pide un candado de Postgres antes de cada vuelta: con dos procesos a la vez
    —un despliegue a media vuelta—, el segundo se la salta. El candado va en una
    conexión propia, sin transacción abierta, y se suelta al acabar; si el
    proceso muere, Postgres lo suelta solo al cerrarse la conexión. Una vuelta
    que falla no para las siguientes.
    """

    def __init__(
        self,
        lanzador: LanzadorEnSegundoPlano,
        esperar: Callable[[float], Awaitable[None]] = asyncio.sleep,
        reloj: Callable[[], datetime] = ahora_en_utc,
    ):
        """El correo es el del lanzador: el mismo para la pasada y para el vigilante."""
        self._lanzador = lanzador
        self._esperar = esperar
        self._reloj = reloj

    async def vigilar(self) -> None:
        """Hasta que la app se apague (se cancela la tarea)."""
        while True:
            try:
                atendidas = await self.vuelta()
                if atendidas:
                    logger.info("Vigilante de hándicaps: %s atendidas", atendidas)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Falló una vuelta del vigilante de hándicaps")
            await self._esperar(INTERVALO_SEGUNDOS)

    async def vuelta(self) -> int | None:
        """Una vuelta, o None si otro proceso tiene el candado."""
        return await con_candado(
            self._lanzador.fabrica.kw["bind"],
            CANDADO_DEL_VIGILANTE,
            VigilarActualizacionesUseCase(
                herramientas=self._lanzador.herramientas,
                lanzador=self._lanzador,
                avisos=self._lanzador.avisos,
                reloj=self._reloj,
            ).execute,
        )
