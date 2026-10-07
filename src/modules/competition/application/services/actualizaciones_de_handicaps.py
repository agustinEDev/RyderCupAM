"""
ActualizacionesDeHandicaps - Cuándo empieza y cuándo se corta una actualización (#251).

Decidido con Agustín el 7 oct 2026:

- **Al cerrar las inscripciones** (desde abiertas) se crea una actualización
  con la RFEG y se lanza en segundo plano. Se cierran por dos caminos: el botón
  de cerrar y, en una Ryder, nombrar a los capitanes.
- **Al iniciar o al reabrir**, la que esté a medias se corta: lo que no se
  actualizó se queda como estaba.

Crear y cortar van dentro de la transacción de quien llama; lanzar, después de
guardar, para que la pasada encuentre la actualización.
"""

from datetime import UTC, datetime

from src.modules.competition.application.exceptions import (
    ActualizacionEnCursoError,
    RefrescoDesactivadoError,
)
from src.modules.competition.application.ports.lanzador_de_actualizaciones import (
    LanzadorDeActualizaciones,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
    OrigenActualizacion,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId


class ActualizacionesDeHandicaps:
    """Crea, corta y lanza las actualizaciones de una competición."""

    def __init__(
        self, uow: CompetitionUnitOfWorkInterface, lanzador: LanzadorDeActualizaciones | None
    ):
        """
        Args:
            uow: La unidad de trabajo de quien llama, ya abierta
            lanzador: La pasada en segundo plano; sin él (fuera de producción) no
                se crea ninguna
        """
        self._uow = uow
        self._lanzador = lanzador

    async def al_cerrar(self, competition_id: CompetitionId) -> ActualizacionDeHandicaps | None:
        """Corta la anterior a medias y crea una nueva, si hay con qué lanzarla."""
        if self._lanzador is None:
            return None
        ahora = datetime.now(UTC)
        await self.cortar(competition_id, ahora)
        actualizacion = ActualizacionDeHandicaps.crear(
            competition_id, OrigenActualizacion.CIERRE, ahora
        )
        await self._uow.handicap_updates.add(actualizacion)
        return actualizacion

    async def a_mano(
        self, competition_id: CompetitionId, origen: OrigenActualizacion, ahora: datetime
    ) -> tuple[ActualizacionDeHandicaps, bool]:
        """
        La que pide el organizador: termina la última si quedó a medias, o empieza otra.

        Returns:
            La actualización, y si es la última reanudada (True) o una nueva

        Raises:
            RefrescoDesactivadoError: Si no hay con qué lanzarla
            ActualizacionEnCursoError: Si ya hay una en marcha
        """
        if self._lanzador is None:
            raise RefrescoDesactivadoError(
                "La actualización con la RFEG solo está encendida en producción."
            )
        ultima = await self._uow.handicap_updates.ultima_de(competition_id)
        if ultima is not None and ultima.sigue():
            raise ActualizacionEnCursoError("Ya se están actualizando los hándicaps.")
        if ultima is not None and ultima.estado is EstadoActualizacion.INCOMPLETA:
            ultima.reanudar()
            await self._uow.handicap_updates.update(ultima)
            return ultima, True
        actualizacion = ActualizacionDeHandicaps.crear(competition_id, origen, ahora)
        await self._uow.handicap_updates.add(actualizacion)
        return actualizacion, False

    async def cortar(self, competition_id: CompetitionId, ahora: datetime | None = None) -> None:
        """La que esté a medias se corta; una completa se queda como está."""
        ultima = await self._uow.handicap_updates.ultima_de(competition_id)
        if ultima is not None:
            ultima.cortar(ahora or datetime.now(UTC))
            await self._uow.handicap_updates.update(ultima)

    def lanzar(self, actualizacion: ActualizacionDeHandicaps | None) -> None:
        """Ya guardada, se lanza: la respuesta no espera a la RFEG."""
        if actualizacion is not None and self._lanzador is not None:
            self._lanzador.lanzar(actualizacion.id)
