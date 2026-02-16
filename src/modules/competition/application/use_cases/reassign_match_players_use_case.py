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
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.golf_course.domain.repositories.golf_course_repository import IGolfCourseRepository
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.repositories.user_repository_interface import UserRepositoryInterface
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender


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

            # Obtener handicap data (tee ratings, holes, user handicaps, genders)
            all_player_ids = [
                UserId(uid)
                for uid in list(request.team_a_player_ids) + list(request.team_b_player_ids)
            ]
            tee_ratings, holes_by_stroke_index, user_handicap_map, user_gender_map = (
                await self._build_handicap_data(round_entity, is_scratch, all_player_ids)
            )

            # 7. Construir nuevos MatchPlayers
            team_a_players = [
                self._build_match_player(
                    uid, enrollment_map, tee_ratings, allowance,
                    is_scratch, user_handicap_map, holes_by_stroke_index, user_gender_map,
                )
                for uid in request.team_a_player_ids
            ]
            team_b_players = [
                self._build_match_player(
                    uid, enrollment_map, tee_ratings, allowance,
                    is_scratch, user_handicap_map, holes_by_stroke_index, user_gender_map,
                )
                for uid in request.team_b_player_ids
            ]

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
        user_handicap_map: dict[str, Decimal] = {}
        user_gender_map: dict[str, Gender | None] = {}

        if not is_scratch:
            golf_course = await self._gc_repo.find_by_id(round_entity.golf_course_id)
            if not golf_course:
                raise ValueError(
                    "Se requiere un campo de golf para el modo HANDICAP. "
                    "Asocie un campo de golf aprobado a la competición."
                )
            total_par = sum(h.par for h in golf_course.holes)
            for tee in golf_course.tees:
                gender_key = tee.gender.value if tee.gender else None
                tee_ratings[(tee.category.value, gender_key)] = TeeRating(
                    course_rating=Decimal(str(tee.course_rating)),
                    slope_rating=tee.slope_rating,
                    par=total_par,
                )
            holes_by_stroke_index = [
                h.number for h in sorted(golf_course.holes, key=lambda h: h.stroke_index)
            ]

            users = await asyncio.gather(
                *(self._user_repo.find_by_id(pid) for pid in all_player_ids)
            )
            for pid, user in zip(all_player_ids, users, strict=True):
                if user:
                    if user.handicap is not None:
                        user_handicap_map[str(pid.value)] = Decimal(str(user.handicap.value))
                    user_gender_map[str(pid.value)] = user.gender

        return tee_ratings, holes_by_stroke_index, user_handicap_map, user_gender_map

    def _build_match_player(
        self, uid_value, enrollment_map, tee_ratings, allowance,
        is_scratch, user_handicap_map, holes_by_stroke_index, user_gender_map,
    ) -> MatchPlayer:
        """Construye un MatchPlayer con handicap calculado y tee auto-resuelto."""
        uid = UserId(uid_value)
        enrollment = enrollment_map.get(str(uid_value))
        if not enrollment:
            raise PlayerNotEnrolledError(
                f"El jugador {uid_value} no tiene inscripción aprobada"
            )
        tee_category = (
            enrollment.tee_category if enrollment.tee_category else TeeCategory.AMATEUR
        )
        user_gender = user_gender_map.get(str(uid_value))

        # Auto-resolve tee: (category, user_gender) → (category, None)
        tee_gender = user_gender
        tee_key = (tee_category.value, tee_gender.value if tee_gender else None)
        if tee_key not in tee_ratings:
            tee_key = (tee_category.value, None)
            tee_gender = None

        if is_scratch:
            return MatchPlayer.create(
                user_id=uid,
                playing_handicap=0,
                tee_category=tee_category,
                strokes_received=[],
                tee_gender=tee_gender,
            )

        # Handicap fallback: custom_handicap > user.handicap > 0
        if enrollment.custom_handicap is not None:
            handicap_index = enrollment.custom_handicap
        elif str(uid_value) in user_handicap_map:
            handicap_index = user_handicap_map[str(uid_value)]
        else:
            handicap_index = Decimal("0")

        tee_rating = tee_ratings.get(tee_key)
        if tee_rating is None:
            raise ValueError(
                f"No se encontró tee rating para el jugador {uid_value} "
                f"(tee_key: {tee_key}) en el campo de golf. "
                f"Verifique que el campo tiene un tee configurado para "
                f"categoría={tee_category.value}, género={tee_gender}"
            )
        playing_handicap = self._calculator.calculate(handicap_index, tee_rating, allowance)
        strokes_received = self._calculator.compute_strokes_received(
            playing_handicap, holes_by_stroke_index
        )
        return MatchPlayer.create(
            user_id=uid,
            playing_handicap=playing_handicap,
            tee_category=tee_category,
            strokes_received=strokes_received,
            tee_gender=tee_gender,
        )

    async def _validate(self, request, user_id):
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

        if not competition.is_creator(user_id):
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

