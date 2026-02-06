"""Caso de Uso: Reasignar jugadores de un partido."""

from decimal import Decimal

from src.modules.competition.application.dto.round_match_dto import (
    ReassignMatchPlayersRequestDTO,
    ReassignMatchPlayersResponseDTO,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_player import MAX_HOLES, MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId


class MatchNotFoundError(Exception):
    """El partido no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """El usuario no es el creador."""

    pass


class MatchNotScheduledError(Exception):
    """El partido no está en estado SCHEDULED."""

    pass


class PlayerNotInTeamError(Exception):
    """Un jugador no pertenece al equipo correcto."""

    pass


class ReassignMatchPlayersUseCase:
    """
    Caso de uso para reasignar jugadores de un partido.

    Solo permitido cuando el partido está en estado SCHEDULED.
    Recalcula los playing handicaps con los nuevos jugadores.
    Crea un nuevo Match con los nuevos jugadores (elimina el anterior).
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
    ):
        self._uow = uow
        self._gc_repo = golf_course_repository
        self._user_repo = user_repository

    async def execute(
        self, request: ReassignMatchPlayersRequestDTO, user_id: UserId
    ) -> ReassignMatchPlayersResponseDTO:
        async with self._uow:
            # 1-4. Validaciones
            match, round_entity, competition = await self._validate(request, user_id)

            # 5. Verificar que los jugadores pertenecen al equipo correcto
            team_assignment = await self._uow.team_assignments.find_by_competition(
                round_entity.competition_id
            )
            self._validate_team_membership(team_assignment, request)

            # 6. Obtener enrollments y campo para recalcular handicaps
            enrollments = await self._uow.enrollments.find_by_competition_and_status(
                round_entity.competition_id, EnrollmentStatus.APPROVED
            )
            enrollment_map = {str(e.user_id.value): e for e in enrollments}

            is_scratch = competition.play_mode == PlayMode.SCRATCH
            allowance = round_entity.get_effective_allowance()
            calculator = PlayingHandicapCalculator()

            # Obtener tee ratings
            tee_ratings = {}
            if not is_scratch:
                golf_course = await self._gc_repo.find_by_id(round_entity.golf_course_id)
                if golf_course:
                    total_par = sum(h.par for h in golf_course.holes)
                    for tee in golf_course.tees:
                        tee_ratings[tee.category.value] = TeeRating(
                            course_rating=Decimal(str(tee.course_rating)),
                            slope_rating=tee.slope_rating,
                            par=total_par,
                        )

            # 7. Construir nuevos MatchPlayers
            def build_player(uid_value):
                uid = UserId(uid_value)
                enrollment = enrollment_map.get(str(uid_value))
                tee_category = (
                    enrollment.tee_category
                    if enrollment and enrollment.tee_category
                    else TeeCategory.AMATEUR_MALE
                )

                if is_scratch:
                    return MatchPlayer.create(
                        user_id=uid, playing_handicap=0,
                        tee_category=tee_category, strokes_received=[],
                    )

                handicap_index = (
                    enrollment.custom_handicap
                    if enrollment and enrollment.custom_handicap is not None
                    else Decimal("0")
                )
                tee_rating = tee_ratings.get(tee_category.value)
                playing_handicap = (
                    calculator.calculate(handicap_index, tee_rating, allowance)
                    if tee_rating else 0
                )
                strokes = (
                    tuple(range(1, playing_handicap + 1))
                    if playing_handicap <= MAX_HOLES
                    else tuple(range(1, MAX_HOLES + 1))
                )
                return MatchPlayer.create(
                    user_id=uid, playing_handicap=playing_handicap,
                    tee_category=tee_category, strokes_received=list(strokes),
                )

            team_a_players = [build_player(uid) for uid in request.team_a_player_ids]
            team_b_players = [build_player(uid) for uid in request.team_b_player_ids]

            # 8. Eliminar partido viejo y crear nuevo
            await self._uow.matches.delete(match.id)

            new_match = Match.create(
                round_id=match.round_id,
                match_number=match.match_number,
                team_a_players=team_a_players,
                team_b_players=team_b_players,
            )
            await self._uow.matches.add(new_match)

        return ReassignMatchPlayersResponseDTO(
            match_id=new_match.id.value,
            new_status=new_match.status.value,
            handicap_strokes_given=new_match.handicap_strokes_given,
            strokes_given_to_team=new_match.strokes_given_to_team,
            updated_at=new_match.updated_at,
        )

    async def _validate(self, request, user_id):
        """Validaciones: buscar match, ronda, competición, verificar creador y estado."""
        match_id = MatchId(request.match_id)
        match = await self._uow.matches.find_by_id(match_id)
        if not match:
            raise MatchNotFoundError(f"No existe partido con ID {request.match_id}")

        if match.status != MatchStatus.SCHEDULED:
            raise MatchNotScheduledError(
                f"Solo se pueden reasignar jugadores en estado SCHEDULED. "
                f"Estado actual: {match.status.value}"
            )

        round_entity = await self._uow.rounds.find_by_id(match.round_id)
        if not round_entity:
            raise MatchNotFoundError("La ronda asociada no existe")

        competition = await self._uow.competitions.find_by_id(round_entity.competition_id)
        if not competition:
            raise MatchNotFoundError("La competición asociada no existe")

        if not competition.is_creator(user_id):
            raise NotCompetitionCreatorError("Solo el creador puede reasignar jugadores")

        return match, round_entity, competition

    @staticmethod
    def _validate_team_membership(team_assignment, request):
        """Verifica que los jugadores pertenecen al equipo correcto."""
        if not team_assignment:
            return

        team_a_set = {str(uid.value) for uid in team_assignment.team_a_player_ids}
        team_b_set = {str(uid.value) for uid in team_assignment.team_b_player_ids}

        for uid in request.team_a_player_ids:
            if str(uid) not in team_a_set:
                raise PlayerNotInTeamError(f"El jugador {uid} no pertenece al equipo A")
        for uid in request.team_b_player_ids:
            if str(uid) not in team_b_set:
                raise PlayerNotInTeamError(f"El jugador {uid} no pertenece al equipo B")
