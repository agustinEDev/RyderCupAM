"""Caso de Uso: Asignar equipos a una competición."""

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
from src.modules.competition.application.services.draft_roster import DraftRoster
from src.modules.competition.application.services.team_assignment_writer import (
    TeamAssignmentWriter,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.snake_draft_service import (
    SnakeDraftService,
    Team,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
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
        self, request: AssignTeamsRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> AssignTeamsResponseDTO:
        async with self._uow:
            # 1. Buscar la competición
            competition_id = CompetitionId(request.competition_id)
            # Con la fila bloqueada, como al nombrar capitanes (BE #320): si no,
            # nombrarlos a la vez guardaria un reparto con los capitanes viejos
            competition = await self._uow.competitions.find_by_id_for_update(competition_id)

            if not competition:
                raise CompetitionNotFoundError(
                    f"No existe competición con ID {request.competition_id}"
                )

            # 2. Verificar creador
            if not is_admin and not competition.is_creator(user_id):
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
            if mode == TeamAssignmentMode.DRAFT:
                # DRAFT no se pide: es lo que queda cuando la sala termina.
                # Admitirlo aqui guardaria un reparto calculado por la
                # aplicacion diciendo que lo eligieron los capitanes
                raise ValueError(
                    "Los equipos de un draft los eligen los capitanes en la sala, "
                    "no se piden por aquí"
                )
            team_a_ids, team_b_ids = await self._repartir(competition, request, enrollments, mode)

            assignment = await TeamAssignmentWriter.guardar(
                self._uow, competition, mode, team_a_ids, team_b_ids
            )

        return AssignTeamsResponseDTO(
            id=assignment.id.value,
            competition_id=assignment.competition_id.value,
            mode=assignment.mode.value,
            team_a_player_ids=[uid.value for uid in assignment.team_a_player_ids],
            team_b_player_ids=[uid.value for uid in assignment.team_b_player_ids],
            created_at=assignment.created_at,
        )

    async def _repartir(self, competition, request, enrollments, mode):
        """Reparte los equipos; las reglas de los capitanes son del dominio (BE #320)."""
        if mode == TeamAssignmentMode.MANUAL:
            team_a_ids, team_b_ids = self._manual_assign(request, enrollments)
            competition.check_captains_placement(team_a_ids, team_b_ids)
            return team_a_ids, team_b_ids

        capitanes = competition.captains_for_team_split()
        players = await self._players_for_draft(enrollments)
        if capitanes is None:
            results = self._draft_service.assign_teams(players)
            return (
                self._draft_service.get_team_players(results, Team.A),
                self._draft_service.get_team_players(results, Team.B),
            )
        return self._draft_service.assign_teams_with_captains(players, *capitanes)

    async def _players_for_draft(self, enrollments):
        """Los jugadores con el hándicap que cuenta para el draft.

        La misma regla que usa la sala de draft (FE #653), en un solo sitio:
        si divergieran, la aplicación elegiría por un capitán con un criterio
        distinto del que usa al repartir sola.
        """
        return await DraftRoster.de_los_inscritos(enrollments, self._user_repo)

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
