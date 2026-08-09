"""Caso de Uso: resumen de rendimiento de un jugador (BE #128)."""

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.stableford_calculator import (
    HoleSetup,
    StablefordCalculator,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.user.application.dto.player_stats_dto import PlayerStatsResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Tope de partidas que se agregan para la media. Sin él, una cuenta con años de
# historial cargaría todos sus scores para calcular un único número.
MAX_ROUNDS_AGGREGATED = 100


class GetPlayerStatsUseCase:
    """
    Agrega el rendimiento de un jugador a partir de los módulos que lo generan.

    Sigue el patrón de `GetAdminStatsUseCase`: los casos de uso de `user`
    reciben las unidades de trabajo de los módulos que consultan, en lugar de
    crear un módulo de lectura aparte.

    Se calcula al vuelo, sin precomputar: el historial de un jugador son unas
    pocas partidas, cambian con cada score anotado, y una estrategia de
    invalidación costaría más que la consulta que ahorra.
    """

    def __init__(
        self,
        user_uow: UserUnitOfWorkInterface,
        competition_uow: CompetitionUnitOfWorkInterface,
        quick_match_uow: QuickMatchUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        stableford_calculator: StablefordCalculator | None = None,
    ):
        self._user_uow = user_uow
        self._competition_uow = competition_uow
        self._quick_match_uow = quick_match_uow
        self._golf_course_uow = golf_course_uow
        self._calculator = stableford_calculator or StablefordCalculator()

    async def execute(
        self, user_id: UserId, golf_course_id: GolfCourseId | None = None
    ) -> PlayerStatsResponseDTO:
        """
        Resumen del jugador, opcionalmente restringido a un campo.

        Con `golf_course_id` solo entran las rondas de ese campo, y los
        contadores de torneos se dejan a cero: son globales del jugador y
        repetirlos en un desglose por campo induciría a error.
        """
        async with self._user_uow:
            user = await self._user_uow.users.find_by_id(user_id)
            handicap = float(user.handicap.value) if user and user.handicap else None

        quick_rounds_played, quick_rounds_to_par = await self._collect_quick_match_rounds(
            user_id, golf_course_id, handicap
        )

        async with self._competition_uow:
            competition_matches = (
                await self._competition_uow.matches.find_completed_for_player(user_id)
            )
            if golf_course_id is not None:
                competition_matches = await self._filter_matches_by_course(
                    competition_matches, golf_course_id
                )

            tournaments_total = 0
            tournaments_active = 0
            if golf_course_id is None:
                enrollments = await self._competition_uow.enrollments.find_by_user(user_id)
                tournaments_total = len(enrollments)
                tournaments_active = (
                    await self._competition_uow.enrollments.count_active_by_user(user_id)
                )

        rounds_played = quick_rounds_played + len(competition_matches)
        scoring_avg = self._average_to_par(quick_rounds_to_par)

        return PlayerStatsResponseDTO(
            handicap=handicap,
            handicap_trend=None,
            scoring_avg=scoring_avg,
            rounds_played=rounds_played,
            tournaments_total=tournaments_total,
            tournaments_active=tournaments_active,
        )

    async def _collect_quick_match_rounds(
        self,
        user_id: UserId,
        golf_course_id: GolfCourseId | None,
        profile_handicap: float | None,
    ) -> tuple[int, list[int]]:
        """
        Rondas rápidas jugadas y su neto respecto al par.

        Se devuelven por separado a propósito: una partida sin scores
        recuperables (campo borrado, vuelta sin anotar) se jugó igual y cuenta
        como ronda, aunque no pueda aportar nada a la media.

        `list_for_user` ya descarta las que el propio usuario ocultó (#127), y
        lo hace por participante: una partida que A ocultó sigue contando para
        B. Esa regla se hereda tal cual en lugar de reimplementarse aquí.
        """
        rounds_played = 0
        results: list[int] = []

        async with self._quick_match_uow, self._golf_course_uow:
            matches = await self._quick_match_uow.quick_matches.list_for_user(
                user_id, status=QuickMatchStatus.COMPLETED, limit=MAX_ROUNDS_AGGREGATED
            )

            for match in matches:
                if golf_course_id is not None and match.golf_course_id != golf_course_id:
                    continue

                participant = self._find_participant(match, user_id)
                if participant is None:
                    continue

                rounds_played += 1

                course = await self._golf_course_uow.golf_courses.find_by_id(match.golf_course_id)
                if course is None:
                    continue

                scores = await self._quick_match_uow.quick_match_hole_scores.find_by_match(
                    match.id
                )
                scores_by_hole = {
                    score.hole_number: score.score
                    for score in scores
                    if score.participant_id == participant.participant_id
                }
                if not scores_by_hole:
                    continue

                holes = [
                    HoleSetup(hole.number, hole.par, hole.stroke_index)
                    for hole in course.holes
                ]
                totals = self._calculator.compute_participant_totals(
                    handicap=self._effective_handicap(participant, profile_handicap),
                    holes=holes,
                    scores_by_hole=scores_by_hole,
                    allowance_percentage=match.get_effective_allowance(),
                )
                results.append(totals.to_par)

        return rounds_played, results

    async def _filter_matches_by_course(self, matches: list, golf_course_id: GolfCourseId) -> list:
        """El campo de un partido vive en su ronda, no en el propio partido."""
        kept = []
        for match in matches:
            round_ = await self._competition_uow.rounds.find_by_id(match.round_id)
            if round_ is not None and round_.golf_course_id == golf_course_id:
                kept.append(match)
        return kept

    @staticmethod
    def _find_participant(match, user_id: UserId):
        return next(
            (p for p in match.participants if p.user_id is not None and p.user_id == user_id),
            None,
        )

    @staticmethod
    def _effective_handicap(participant, profile_handicap: float | None) -> float | None:
        """
        Hándicap con el que jugó, por orden: el override manual que puso el
        creador, y si no el del perfil.

        Un participante registrado lleva `handicap` a None a propósito: el suyo
        vive en su perfil, no copiado en la partida. Solo los invitados, que no
        tienen cuenta, lo traen dentro.
        """
        if participant.custom_handicap is not None:
            return participant.custom_handicap
        return profile_handicap

    @staticmethod
    def _average_to_par(rounds_to_par: list[int]) -> float | None:
        """None sin rondas: no hay media que dar, que no es una media de cero."""
        if not rounds_to_par:
            return None
        return round(sum(rounds_to_par) / len(rounds_to_par), 1)
