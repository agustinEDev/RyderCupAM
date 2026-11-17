"""
Caso de Uso: El estado de la actualización de hándicaps, para la ficha (#251).

Si una actualización con la RFEG deja a alguien sin actualizar, se avisa al
organizador por correo y también en la competición (decidido el 7 oct 2026):
la ficha le dice cómo va la última y quién falta. Solo al organizador o a un
administrador. No escribe nada: es una pregunta.

Desde el 15 nov 2026 también lleva la lista del aviso «{N} jugadores sin
actualizar con la RFEG», con la misma regla (`SinActualizarDeLaCompeticion`):
el aviso lleva a esta ficha y tiene que nombrar a los mismos. Como el aviso,
solo con la competición cerrada (al empezar desaparece, H5). Va aparte de
`pending_players`, que sigue siendo quién falta por preguntar (lo que el botón
termina) y lo que lee el front que ya está en producción.

Las dos listas y sus nombres salen de una sola lectura de inscritos, de lo
apuntado y de sus usuarios; y si no hace falta ninguna, no se lee nada más.
"""

from src.modules.competition.application.dto.competition_dto import (
    HandicapUpdateStatusDTO,
    PendingHandicapPlayerDTO,
)
from src.modules.competition.application.services.pendientes_de_actualizar import (
    PendientesDeActualizar,
)
from src.modules.competition.application.services.player_names import PlayerNames
from src.modules.competition.application.services.sin_actualizar_de_la_competicion import (
    SinActualizarDeLaCompeticion,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    EstadoActualizacion,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
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
            # Como el aviso: terminada y con la competición cerrada (H1, H5)
            con_lista = competicion.status is CompetitionStatus.CLOSED and (
                SinActualizarDeLaCompeticion.terminada(actualizacion)
            )
            con_pendientes = actualizacion.estado in CON_PENDIENTES
            pendientes: list[UserId] = []
            sin_actualizar: list[UserId] = []
            nombres: dict[UserId, str] = {}
            if con_pendientes or con_lista:
                inscritos = await self._uow.enrollments.find_by_competition_and_status(
                    competition_id, EnrollmentStatus.APPROVED
                )
                resultados = await self._uow.handicap_updates.resultados(actualizacion.id)
                usuarios = {
                    u.id: u for u in await self._users.find_by_ids([i.user_id for i in inscritos])
                }
                if con_pendientes:
                    pendientes = PendientesDeActualizar.de_lo_leido(inscritos, resultados)
                if con_lista:
                    sin_actualizar = SinActualizarDeLaCompeticion.de_lo_leido(
                        competicion, actualizacion, inscritos, usuarios, resultados
                    ).para_el_organizador
                nombres = PlayerNames.de_lo_leido(
                    list(dict.fromkeys([*pendientes, *sin_actualizar])),
                    usuarios,
                    inscritos,
                    competicion.visibility,
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
            not_updated_players=[
                PendingHandicapPlayerDTO(user_id=u.value, name=nombres.get(u, ""))
                for u in sin_actualizar
            ],
        )
