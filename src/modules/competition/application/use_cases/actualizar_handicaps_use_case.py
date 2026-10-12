"""
Casos de Uso: El botón «Actualizar hándicaps» y su ventana (#251).

Decidido con Agustín el 7 oct 2026. Además del refresco al cerrar las
inscripciones, el organizador puede pedir a la RFEG los hándicaps de sus
jugadores:

- Desde el cierre hasta 10 s por jugador antes de la siguiente salida, nunca
  con una jornada en marcha; en una Ryder, del cierre a iniciar.
- Si la última quedó a medias, **termina solo lo que falta**; si no, pregunta
  por todos.
- Ya empezado un stroke play, cambia el hándicap para lo que falta por jugar;
  la categoría se queda la del cierre.
"""

from collections.abc import Callable
from datetime import datetime

from src.modules.competition.application.dto.competition_dto import HandicapUpdateWindowDTO
from src.modules.competition.application.exceptions import (
    ActualizacionNoPermitidaError,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.ports.lanzador_de_actualizaciones import (
    LanzadorDeActualizaciones,
)
from src.modules.competition.application.services.actualizaciones_de_handicaps import (
    ActualizacionesDeHandicaps,
)
from src.modules.competition.application.services.ventana_de_la_competicion import ventana_de
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    OrigenActualizacion,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class ActualizarHandicapsUseCase:
    """El organizador pide a la RFEG los hándicaps de sus jugadores."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone,
        lanzador: LanzadorDeActualizaciones | None,
        reloj: Callable[[], datetime],
    ):
        self._uow = uow
        self._zonas = zonas
        self._actualizaciones = ActualizacionesDeHandicaps(uow, lanzador)
        self._reloj = reloj

    async def execute(
        self, competition_id: CompetitionId, user_id: UserId, is_admin: bool = False
    ) -> tuple[ActualizacionDeHandicaps, bool]:
        """
        Returns:
            La actualización lanzada, y si es la incompleta reanudada (True) o nueva

        Raises:
            CompetitionNotFoundError, NotCompetitionCreatorError,
            ActualizacionNoPermitidaError: fuera de la ventana, con el motivo,
            ActualizacionEnCursoError: si ya hay una,
            RefrescoDesactivadoError: fuera de producción
        """
        ahora = self._reloj()
        async with self._uow:
            # Bloqueada: iniciar, cerrar o reabrir a la vez esperan
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if competition is None:
                raise CompetitionNotFoundError(f"No existe la competición {competition_id}")
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError(
                    "Solo el organizador puede actualizar los hándicaps"
                )
            ventana = await ventana_de(self._uow, self._zonas, competition, ahora)
            if not ventana.abierta:
                raise ActualizacionNoPermitidaError(ventana.motivo)
            actualizacion, reanudada = await self._actualizaciones.a_mano(
                competition_id, OrigenActualizacion.BOTON, ahora
            )
        self._actualizaciones.lanzar(actualizacion)
        return actualizacion, reanudada


class VentanaDeActualizacionUseCase:
    """Para la ficha: si el organizador puede actualizar ahora, y hasta cuándo."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone,
        reloj: Callable[[], datetime],
        refresco_activo: bool = True,
    ):
        """
        Args:
            refresco_activo: Si hay con qué lanzarla: fuera de producción, el
                botón sale apagado y no responde 409 al pulsarlo
        """
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj
        self._refresco_activo = refresco_activo

    async def execute(
        self, competition_id: CompetitionId, user_id: UserId, is_admin: bool = False
    ) -> HandicapUpdateWindowDTO | None:
        """None si quien mira no organiza la competición (ni es admin)."""
        async with self._uow:
            competition = await self._uow.competitions.find_by_id(competition_id)
            if competition is None or not (is_admin or competition.is_creator(user_id)):
                return None
            programada = await self._uow.handicap_updates.programada_de(competition_id)
            ventana = await self._ventana(competition)
        return ventana.model_copy(update={"scheduled_at": programada})

    async def _ventana(self, competition: Competition) -> HandicapUpdateWindowDTO:
        """El botón: apagado, con el motivo, cuando pulsarlo solo daría un 409."""
        if not self._refresco_activo:
            return HandicapUpdateWindowDTO(
                open=False,
                reason="La actualización con la RFEG solo está encendida en producción.",
            )
        ultima = await self._uow.handicap_updates.ultima_de(competition.id)
        if ultima is not None and ultima.sigue():
            return HandicapUpdateWindowDTO(
                open=False, reason="Ya se están actualizando los hándicaps."
            )
        ventana = await ventana_de(self._uow, self._zonas, competition, self._reloj())
        return HandicapUpdateWindowDTO(
            open=ventana.abierta, closes_at=ventana.cierra, reason=ventana.motivo
        )
