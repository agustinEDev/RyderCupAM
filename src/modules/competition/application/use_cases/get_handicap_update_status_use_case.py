"""
Caso de Uso: El estado de la actualización de hándicaps, para la ficha (#251).

Si una actualización con la RFEG deja a alguien sin actualizar, se avisa al
organizador por correo y también en la competición (decidido el 7 oct 2026):
la ficha le dice cómo va la última y quién falta. Solo al organizador o a un
administrador. No escribe nada: es una pregunta.
"""

from src.modules.competition.application.dto.competition_dto import (
    HandicapUpdateStatusDTO,
    PendingHandicapPlayerDTO,
)
from src.modules.competition.application.services.pendientes_de_actualizar import (
    PendientesDeActualizar,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    EstadoActualizacion,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Solo en estas tiene sentido decir quién falta: en las otras ya no se actualiza
CON_PENDIENTES = {EstadoActualizacion.EN_CURSO, EstadoActualizacion.INCOMPLETA}


class GetHandicapUpdateStatusUseCase:
    """La última actualización de hándicaps de una competición, para quien la organiza."""

    def __init__(
        self, uow: CompetitionUnitOfWorkInterface, user_repository: UserRepositoryInterface
    ):
        self._uow = uow
        self._users = user_repository

    async def execute(
        self, competition_id: CompetitionId, user_id: UserId, is_admin: bool = False
    ) -> HandicapUpdateStatusDTO | None:
        """
        Returns:
            Su estado y quién falta, o None si no hay ninguna o quien mira no organiza
        """
        async with self._uow:
            competicion = await self._uow.competitions.find_by_id(competition_id)
            if competicion is None or not (is_admin or competicion.is_creator(user_id)):
                return None
            actualizacion = await self._uow.handicap_updates.ultima_de(competition_id)
            if actualizacion is None:
                return None
            pendientes = []
            if actualizacion.estado in CON_PENDIENTES:
                pendientes = await PendientesDeActualizar.de(self._uow, actualizacion)
            nombres = await PlayerNames.de_la_competicion(
                pendientes, competition_id, self._users, self._uow
            )
        return HandicapUpdateStatusDTO(
            status=actualizacion.estado.value,
            origin=actualizacion.origen.value,
            started_at=actualizacion.creada,
            finished_at=actualizacion.terminada,
            pending_players=[
                PendingHandicapPlayerDTO(user_id=u.value, name=nombres.get(u, ""))
                for u in pendientes
            ],
        )
