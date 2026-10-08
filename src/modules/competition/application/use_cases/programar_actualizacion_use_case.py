"""
Casos de Uso: Programar y anular la actualización de hándicaps (#251).

Decidido con Agustín el 7 oct 2026: el organizador puede dejar programada la
actualización con la RFEG (por ejemplo a las 3:00, cuando ya han publicado),
una por competición, y cambiarla o anularla hasta su hora. Tiene que caer
dentro de la ventana del botón, mirada en esa hora. La lanza el vigilante; si
al llegar la ventana está cerrada, no se lanza y se avisa al organizador.
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from src.modules.competition.application.exceptions import (
    ActualizacionNoPermitidaError,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    RefrescoDesactivadoError,
)
from src.modules.competition.application.ports.competition_timezone import (
    ICompetitionTimezone,
)
from src.modules.competition.application.services.ventana_de_la_competicion import ventana_de
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId

# El vigilante pasa cada minuto y la vuelta tarda: lo programado tiene que caber
# con este margen dentro de la ventana
MARGEN = timedelta(minutes=2)


async def _del_organizador(
    uow: CompetitionUnitOfWorkInterface,
    competition_id: CompetitionId,
    user_id: UserId,
    is_admin: bool,
) -> Competition:
    competition = await uow.competitions.find_by_id_for_update(competition_id)
    if competition is None:
        raise CompetitionNotFoundError(f"No existe la competición {competition_id}")
    if not is_admin and not competition.is_creator(user_id):
        raise NotCompetitionCreatorError("Solo el organizador puede programar la actualización")
    return competition


class ProgramarActualizacionUseCase:
    """Programa (o reprograma) la actualización de hándicaps de una competición."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        zonas: ICompetitionTimezone,
        reloj: Callable[[], datetime],
        refresco_activo: bool,
    ):
        self._uow = uow
        self._zonas = zonas
        self._reloj = reloj
        self._refresco_activo = refresco_activo

    async def execute(
        self,
        competition_id: CompetitionId,
        user_id: UserId,
        para: datetime,
        is_admin: bool = False,
    ) -> datetime:
        """
        Returns:
            Para cuándo queda programada

        Raises:
            CompetitionNotFoundError, NotCompetitionCreatorError,
            RefrescoDesactivadoError: fuera de producción,
            ActualizacionNoPermitidaError: en el pasado o fuera de la ventana
        """
        ahora = self._reloj()
        async with self._uow:
            competition = await _del_organizador(self._uow, competition_id, user_id, is_admin)
            if not self._refresco_activo:
                raise RefrescoDesactivadoError(
                    "La actualización con la RFEG solo está encendida en producción."
                )
            if para <= ahora:
                raise ActualizacionNoPermitidaError("Prográmala para un momento en el futuro.")
            ventana = await ventana_de(self._uow, self._zonas, competition, para)
            if not ventana.abierta:
                raise ActualizacionNoPermitidaError(f"A esa hora no se podría: {ventana.motivo}")
            # El vigilante pasa cada minuto: tiene que seguir abierta un rato después
            con_margen = await ventana_de(self._uow, self._zonas, competition, para + MARGEN)
            if not con_margen.abierta:
                raise ActualizacionNoPermitidaError(
                    "Demasiado justo: prográmala con al menos "
                    f"{int(MARGEN.total_seconds() // 60)} minutos de margen antes de que "
                    "se cierre la ventana."
                )
            await self._uow.handicap_updates.programar(competition_id, para, ahora)
        return para


class AnularProgramacionUseCase:
    """Quita la actualización programada de una competición."""

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, competition_id: CompetitionId, user_id: UserId, is_admin: bool = False
    ) -> None:
        """
        Raises:
            CompetitionNotFoundError, NotCompetitionCreatorError
        """
        async with self._uow:
            await _del_organizador(self._uow, competition_id, user_id, is_admin)
            await self._uow.handicap_updates.anular_programada(competition_id)
