"""Caso de Uso: Asignar equipos a una competición."""

from decimal import Decimal

from src.modules.competition.application.dto.round_match_dto import (
    AssignTeamsRequestDTO,
    AssignTeamsResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotClosedError,
    CompetitionNotFoundError,
    InsufficientPlayersError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.snake_draft_service import (
    PlayerForDraft,
    SnakeDraftService,
    Team,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.team_assignment_mode import TeamAssignmentMode
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId


class OddPlayersError(Exception):
    """Número impar de jugadores (no se pueden balancear)."""

    pass


class PlayerNotEnrolledError(Exception):
    """Un jugador de la asignación manual no está inscrito."""

    pass


class DuplicatePlayerInTeamsError(Exception):
    """Un jugador aparece en ambos equipos."""

    pass


class AssignTeamsUseCase:
    """
    Caso de uso para asignar equipos.

    AUTOMATIC: usa SnakeDraftService con handicaps de los jugadores.
    MANUAL: usa las listas proporcionadas, verificando que todos son enrollees.

    Si ya existe una asignación previa, la elimina (re-asignación).
    Transiciona todas las rondas PENDING_TEAMS → PENDING_MATCHES.
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_repository: UserRepositoryInterface,
        snake_draft_service: SnakeDraftService | None = None,
    ):
        self._uow = uow
        self._user_repo = user_repository
        self._draft_service = snake_draft_service or SnakeDraftService()

    async def execute(
        self, request: AssignTeamsRequestDTO, user_id: UserId
    ) -> AssignTeamsResponseDTO:
        async with self._uow:
            # 1. Buscar la competición
            competition_id = CompetitionId(request.competition_id)
            competition = await self._uow.competitions.find_by_id(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar creador
            if not competition.is_creator(user_id):
                raise NotCompetitionCreatorError("Solo el creador puede asignar equipos")

            # 3. Verificar estado CLOSED
            if competition.status != CompetitionStatus.CLOSED:
                raise CompetitionNotClosedError(
                    f"La competición debe estar en estado CLOSED. "
                    f"Estado actual: {competition.status.value}"
                )

            # 4. Obtener enrollments aprobados
            enrollments = await self._uow.enrollments.find_by_competition_and_status(
                competition_id, EnrollmentStatus.APPROVED
            )

            MIN_PLAYERS = 2  # noqa: N806
            if len(enrollments) < MIN_PLAYERS:
                raise InsufficientPlayersError(
                    f"Se necesitan al menos 2 jugadores aprobados. Hay {len(enrollments)}"
                )

            if len(enrollments) % 2 != 0:
                raise OddPlayersError(
                    f"Se necesita un número par de jugadores. Hay {len(enrollments)}"
                )

            mode = TeamAssignmentMode(request.mode)

            if mode == TeamAssignmentMode.AUTOMATIC:
                team_a_ids, team_b_ids = await self._auto_assign(enrollments)
            else:
                team_a_ids, team_b_ids = self._manual_assign(request, enrollments)

            # 5. Eliminar asignación previa si existe (re-asignación)
            existing = await self._uow.team_assignments.find_by_competition(competition_id)
            if existing:
                await self._uow.team_assignments.delete(existing.id)

            # 6. Crear TeamAssignment
            assignment = TeamAssignment.create(
                competition_id=competition_id,
                mode=mode,
                team_a_player_ids=team_a_ids,
                team_b_player_ids=team_b_ids,
            )
            await self._uow.team_assignments.add(assignment)

            # 7. Transicionar rondas PENDING_TEAMS → PENDING_MATCHES
            rounds = await self._uow.rounds.find_by_competition(competition_id)
            for round_entity in rounds:
                if round_entity.status == RoundStatus.PENDING_TEAMS:
                    round_entity.mark_teams_assigned()
                    await self._uow.rounds.update(round_entity)

        return AssignTeamsResponseDTO(
            id=assignment.id.value,
            competition_id=assignment.competition_id.value,
            mode=assignment.mode.value,
            team_a_player_ids=[uid.value for uid in assignment.team_a_player_ids],
            team_b_player_ids=[uid.value for uid in assignment.team_b_player_ids],
            created_at=assignment.created_at,
        )

    async def _auto_assign(self, enrollments):
        """Asignación automática usando SnakeDraftService."""
        players = []
        for enrollment in enrollments:
            # Obtener handicap: custom_handicap > User.handicap > 0
            if enrollment.custom_handicap is not None:
                handicap = enrollment.custom_handicap
            else:
                user = await self._user_repo.find_by_id(enrollment.user_id)
                if user and user.handicap is not None:
                    handicap = Decimal(str(user.handicap.value))
                else:
                    handicap = Decimal("0")
            players.append(PlayerForDraft(user_id=enrollment.user_id, handicap=handicap))

        results = self._draft_service.assign_teams(players)

        team_a_ids = self._draft_service.get_team_players(results, Team.A)
        team_b_ids = self._draft_service.get_team_players(results, Team.B)
        return team_a_ids, team_b_ids

    def _manual_assign(self, request, enrollments):
        """Asignación manual con validación."""
        if not request.team_a_player_ids or not request.team_b_player_ids:
            raise ValueError(
                "Para modo MANUAL, se deben proporcionar team_a_player_ids y team_b_player_ids"
            )

        # Validar que no hay jugadores en ambos equipos
        overlap = {str(uid) for uid in request.team_a_player_ids} & {
            str(uid) for uid in request.team_b_player_ids
        }
        if overlap:
            raise DuplicatePlayerInTeamsError(
                f"Los siguientes jugadores aparecen en ambos equipos: {overlap}"
            )

        enrolled_user_ids = {str(e.user_id.value) for e in enrollments}

        team_a_ids = []
        for uid in request.team_a_player_ids:
            if str(uid) not in enrolled_user_ids:
                raise PlayerNotEnrolledError(f"El jugador {uid} no está inscrito como APPROVED")
            team_a_ids.append(UserId(uid))

        team_b_ids = []
        for uid in request.team_b_player_ids:
            if str(uid) not in enrolled_user_ids:
                raise PlayerNotEnrolledError(f"El jugador {uid} no está inscrito como APPROVED")
            team_b_ids.append(UserId(uid))

        return team_a_ids, team_b_ids
