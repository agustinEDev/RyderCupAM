"""Caso de Uso: Reasignar jugadores de un partido."""

import asyncio
from decimal import Decimal

from src.modules.competition.application.dto.round_match_dto import (
    ReassignMatchPlayersRequestDTO,
    ReassignMatchPlayersResponseDTO,
)
from src.modules.competition.application.exceptions import (
    MatchNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.services.course_context import course_context_for
from src.modules.competition.application.services.match_players_builder import (
    MatchPlayersBuilder,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
)
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode


class MatchNotScheduledError(Exception):
    """El partido no esta en estado SCHEDULED."""

    pass


class PlayerNotInTeamError(Exception):
    """Un jugador no pertenece al equipo correcto."""

    pass


class NoTeamAssignmentError(Exception):
    """No hay asignación de equipos."""

    pass


class PlayerNotEnrolledError(Exception):
    """El jugador no tiene inscripción aprobada."""

    pass


class WrongNumberOfPlayersError(Exception):
    """Un lado no trae los jugadores que pide el formato del partido."""

    pass


class ReassignMatchPlayersUseCase:
    """
    Caso de uso para reasignar jugadores de un partido.

    Solo permitido cuando el partido esta en estado SCHEDULED.
    Recalcula los playing handicaps con los nuevos jugadores.
    Crea un nuevo Match con los nuevos jugadores (elimina el anterior).
    """

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        golf_course_repository: IGolfCourseRepository,
        user_repository: UserRepositoryInterface,
        handicap_calculator: PlayingHandicapCalculator | None = None,
    ):
        self._uow = uow
        self._gc_repo = golf_course_repository
        self._user_repo = user_repository
        self._calculator = handicap_calculator or PlayingHandicapCalculator()
        self._match_players = MatchPlayersBuilder()

    async def execute(
        self, request: ReassignMatchPlayersRequestDTO, user_id: UserId, is_admin: bool = False
    ) -> ReassignMatchPlayersResponseDTO:
        async with self._uow:
            # 1-4. Validaciones
            match, round_entity, competition = await self._validate(request, user_id, is_admin)

            # 5. Verificar que los jugadores pertenecen al equipo correcto
            team_assignment = await self._uow.team_assignments.find_by_competition(
                round_entity.competition_id
            )
            self._validate_team_membership(team_assignment, request)

            # 5b. Cada lado, exactamente los jugadores de su formato. El reparto
            #     individual lee el primero de cada lado: sin esto, un 2 contra 2
            #     en individual se guardaba en silencio como 1 contra 1.
            per_side = round_entity.match_format.players_per_team()
            if (
                len(request.team_a_player_ids) != per_side
                or len(request.team_b_player_ids) != per_side
            ):
                raise WrongNumberOfPlayersError(
                    f"Un partido {round_entity.match_format.value} lleva {per_side} "
                    f"jugador(es) por equipo; llegaron {len(request.team_a_player_ids)} "
                    f"y {len(request.team_b_player_ids)}"
                )
            # Y distintos: dos plazas con el mismo jugador lo guardaban repetido
            # en su equipo (en foursomes, la media salía solo de su hándicap)
            for side in (request.team_a_player_ids, request.team_b_player_ids):
                if len(set(side)) != len(side):
                    raise WrongNumberOfPlayersError("Hay un jugador repetido en el mismo equipo")

            # 6. Obtener enrollments y campo para recalcular handicaps
            enrollments = await self._uow.enrollments.find_by_competition_and_status(
                round_entity.competition_id, EnrollmentStatus.APPROVED
            )
            enrollment_map = {str(e.user_id.value): e for e in enrollments}

            is_scratch = competition.play_mode == PlayMode.SCRATCH
            allowance = round_entity.get_effective_allowance()

            # Obtener handicap data (tee ratings, holes, user handicaps, genders)
            all_player_ids = [
                UserId(uid)
                for uid in list(request.team_a_player_ids) + list(request.team_b_player_ids)
            ]
            (
                tee_ratings,
                holes_by_stroke_index,
                user_handicap_map,
                user_gender_map,
                holes_by_tee,
            ) = await self._build_handicap_data(round_entity, is_scratch, all_player_ids)

            # 7. Construir nuevos MatchPlayers, con el reparto de su formato:
            #    el mismo que al generar (BE #477). Sin inscripción aprobada no
            #    se sabe desde qué barra juega ni con qué hándicap.
            for uid in [*request.team_a_player_ids, *request.team_b_player_ids]:
                if str(uid) not in enrollment_map:
                    raise PlayerNotEnrolledError(f"El jugador {uid} no tiene inscripción aprobada")
            team_a_players, team_b_players = self._match_players.build(
                round_entity.match_format,
                [UserId(uid) for uid in request.team_a_player_ids],
                [UserId(uid) for uid in request.team_b_player_ids],
                enrollment_map,
                tee_ratings,
                self._calculator,
                allowance,
                is_scratch,
                user_handicap_map,
                holes_by_stroke_index,
                user_gender_map,
                competition.max_playing_handicap,
                holes_by_tee,
            )

            # 8. Eliminar partido viejo y crear nuevo
            await self._uow.matches.delete(match.id)
            await self._uow.flush()  # Flush DELETE before INSERT (unique constraint)

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
                strokes_given_to_team=new_match.strokes_given_to_team or "",
                updated_at=new_match.updated_at,
            )

    async def _build_handicap_data(self, round_entity, is_scratch, all_player_ids):
        """Pre-fetch tee ratings, hole stroke order, user handicaps, and user genders."""
        tee_ratings: dict[tuple[str, str | None], TeeRating] = {}
        holes_by_stroke_index: list[int] = []
        holes_by_tee: dict[tuple[str, str | None], list[int]] = {}
        user_handicap_map: dict[str, Decimal] = {}
        user_gender_map: dict[str, Gender | None] = {}

        if not is_scratch:
            golf_course = await self._gc_repo.find_by_id(round_entity.golf_course_id)
            if not golf_course:
                raise ValueError(
                    "Se requiere un campo de golf para el modo HANDICAP. "
                    "Asocie un campo de golf aprobado a la competición."
                )
            context = course_context_for(golf_course)
            tee_ratings = context.tee_ratings
            holes_by_stroke_index = context.holes_by_stroke_index
            holes_by_tee = context.holes_by_tee

            users = await asyncio.gather(
                *(self._user_repo.find_by_id(pid) for pid in all_player_ids)
            )
            for pid, user in zip(all_player_ids, users, strict=True):
                if user:
                    if user.handicap is not None:
                        user_handicap_map[str(pid.value)] = Decimal(str(user.handicap.value))
                    user_gender_map[str(pid.value)] = user.gender

        return (
            tee_ratings,
            holes_by_stroke_index,
            user_handicap_map,
            user_gender_map,
            holes_by_tee,
        )

    async def _validate(self, request, user_id, is_admin: bool = False):
        """Validaciones: buscar match, ronda, competicion, verificar creador y estado."""
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
            raise MatchNotFoundError("La competicion asociada no existe")

        if not is_admin and not competition.is_creator(user_id):
            raise NotCompetitionCreatorError("Solo el creador puede reasignar jugadores")

        return match, round_entity, competition

    @staticmethod
    def _validate_team_membership(team_assignment, request):
        """Verifica que los jugadores pertenecen al equipo correcto."""
        if not team_assignment:
            raise NoTeamAssignmentError(
                "No hay asignación de equipos. Use AssignTeamsUseCase primero."
            )

        team_a_set = {str(uid.value) for uid in team_assignment.team_a_player_ids}
        team_b_set = {str(uid.value) for uid in team_assignment.team_b_player_ids}

        for uid in request.team_a_player_ids:
            if str(uid) not in team_a_set:
                raise PlayerNotInTeamError(f"El jugador {uid} no pertenece al equipo A")
        for uid in request.team_b_player_ids:
            if str(uid) not in team_b_set:
                raise PlayerNotInTeamError(f"El jugador {uid} no pertenece al equipo B")
