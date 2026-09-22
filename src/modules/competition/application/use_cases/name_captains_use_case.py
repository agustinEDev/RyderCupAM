"""
Caso de Uso: Nombrar a los capitanes (BE #320).

Nadie quiere pulsar «cerrar inscripciones», pero nombrar a los capitanes si es
algo que el organizador quiere hacer, y es lo que de verdad congela la
plantilla: con las inscripciones abiertas, nombrarlos las cierra.
"""

from src.modules.competition.application.dto.competition_dto import (
    NameCaptainsRequestDTO,
    NameCaptainsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.user.domain.value_objects.user_id import UserId


class NameCaptainsUseCase:
    """
    Caso de uso para nombrar a los dos capitanes de una competicion.

    Solo el creador o un administrador. Las reglas del nombramiento —dos
    inscritos aprobados distintos, en ACTIVE o CLOSED, sin equipos repartidos—
    son de la entidad: aqui se traen los datos de los otros agregados.

    Con un numero impar de inscritos se avisa y se deja seguir (decidido el 20
    sep): quedarse atascado la vispera es peor que un torneo desigual.
    """

    def __init__(self, uow: CompetitionUnitOfWorkInterface):
        """
        Constructor.

        Args:
            uow: Unit of Work para gestionar transacciones
        """
        self._uow = uow

    async def execute(
        self, request: NameCaptainsRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> NameCaptainsResponseDTO:
        """
        Nombra a los capitanes y, si las inscripciones siguen abiertas, las cierra.

        Args:
            request: La competicion y los dos capitanes
            user_id: Quien los nombra
            is_admin: Si es administrador

        Returns:
            Los capitanes, el estado y el aviso de numeros que no cuadran

        Raises:
            CompetitionNotFoundError: Si la competicion no existe
            NotCompetitionCreatorError: Si no es el creador ni admin
            CaptainNotEnrolledError: Si alguno no es un inscrito aprobado
            CaptainsLockedError: Si ya hay equipos repartidos
            CompetitionStateError: Si no esta en ACTIVE ni en CLOSED
            ValueError: Si es la misma persona
        """
        async with self._uow:
            # Con la fila bloqueada, como el cupo en handle_enrollment: una
            # inscripcion aprobada a la vez se colaria en el recuento y en el
            # aviso, y entraria despues de cerrar
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)
            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )
            if not is_admin and not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede nombrar a los capitanes")

            team_a = UserId(request.team_a_captain_id)
            team_b = UserId(request.team_b_captain_id)
            aprobados = {
                e.user_id
                for e in await self._uow.enrollments.find_by_competition_and_status(
                    competition_id, EnrollmentStatus.APPROVED
                )
            }
            reparto = await self._uow.team_assignments.find_by_competition(competition_id)
            competition.name_captains(
                team_a, team_b, approved_player_ids=aprobados, has_teams=reparto is not None
            )
            await self._uow.competitions.update(competition)

        return NameCaptainsResponseDTO(
            id=competition.id.value,
            status=competition.status.value,
            team_a_captain_id=team_a.value,
            team_b_captain_id=team_b.value,
            total_players=len(aprobados),
            uneven_teams=len(aprobados) % 2 != 0,
        )
