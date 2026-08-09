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

    Solo cuentan las **vueltas enteras de partidas terminadas**: partida a
    medias, tarjeta a medias o hoyo sin anotar quedan fuera, tanto de la media
    como del contador de rondas. Media docena de vueltas comparables valen más
    que veinte a medio anotar, y un `rounds_played` que incluyera rondas que no
    entran en la media daría dos números que no cuadran entre sí.

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

        quick_rounds_to_par = await self._collect_quick_match_rounds(
            user_id, golf_course_id, handicap
        )

        async with self._competition_uow:
            competition_matches = (
                await self._competition_uow.matches.find_completed_for_player(user_id)
            )
            rounds_by_match = await self._rounds_by_match(competition_matches)
            if golf_course_id is not None:
                competition_matches = [
                    match
                    for match in competition_matches
                    if self._match_course(match, rounds_by_match) == golf_course_id
                ]
            scorecards = {
                match.id: await self._competition_uow.hole_scores.find_by_match_and_player(
                    match.id, user_id
                )
                for match in competition_matches
            }

            tournaments_total = 0
            tournaments_active = 0
            if golf_course_id is None:
                enrollments = await self._competition_uow.enrollments.find_by_user(user_id)
                tournaments_total = len(enrollments)
                tournaments_active = (
                    await self._competition_uow.enrollments.count_active_by_user(user_id)
                )

        competition_rounds_to_par = await self._collect_competition_rounds(
            competition_matches, rounds_by_match, scorecards
        )

        computable_rounds = quick_rounds_to_par + competition_rounds_to_par
        rounds_played = len(computable_rounds)
        scoring_avg = self._average_to_par(computable_rounds)

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
    ) -> list[int]:
        """
        Neto respecto al par de cada vuelta rápida computable.

        Solo entran las partidas terminadas con la tarjeta entera: una vuelta a
        medias no se puede comparar con una completa, y con el campo borrado no
        hay ni pares contra los que medirla.

        `list_for_user` ya descarta las que el propio usuario ocultó (#127), y
        lo hace por participante: una partida que A ocultó sigue contando para
        B. Esa regla se hereda tal cual en lugar de reimplementarse aquí.
        """
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
                if not self._is_full_scorecard(scores_by_hole, course):
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
                    # La media junta partidas rápidas y torneo: si solo una de
                    # las dos topara los hoyos malos, no serían comparables
                    cap_at_net_double_bogey=True,
                )
                results.append(totals.to_par)

        return results

    @staticmethod
    def _is_full_scorecard(scores_by_hole: dict, course) -> bool:
        """
        La tarjeta está entera cuando ningún hoyo del campo se quedó sin anotar.

        Se compara contra los hoyos que tiene el campo y no contra un 18 fijo:
        el día que se admitan campos de nueve, la regla sigue siendo la misma.
        """
        return all(hole.number in scores_by_hole for hole in course.holes)

    async def _rounds_by_match(self, matches: list) -> dict:
        """
        La ronda de cada partido, una consulta por ronda distinta.

        Hace falta para dos cosas que el partido no sabe por sí solo: en qué
        campo se jugó y con qué pares se compara su tarjeta.
        """
        rounds: dict = {}
        by_match: dict = {}
        for match in matches:
            if match.round_id not in rounds:
                rounds[match.round_id] = await self._competition_uow.rounds.find_by_id(
                    match.round_id
                )
            by_match[match.id] = rounds[match.round_id]
        return by_match

    @staticmethod
    def _match_course(match, rounds_by_match: dict) -> GolfCourseId | None:
        round_ = rounds_by_match.get(match.id)
        return round_.golf_course_id if round_ is not None else None

    async def _collect_competition_rounds(
        self, matches: list, rounds_by_match: dict, scorecards: dict
    ) -> list[int]:
        """
        Neto respecto al par de cada tarjeta de torneo.

        El formato del partido da igual: en match play también firmas una
        tarjeta con tus golpes, y esa tarjeta dice a qué nivel jugaste tan bien
        como la de una vuelta de medal. Solo entran las que estén enteras.

        Se usa `own_score`, no el `net_score` de la entidad: ese solo se calcula
        cuando el marcador ha validado el hoyo, así que media tarjeta legítima
        se quedaría fuera por no haberse cerrado la validación cruzada. Los
        golpes recibidos ya vienen resueltos por hoyo desde que se generó el
        partido, sin repartirlos aquí otra vez.
        """
        results: list[int] = []
        courses: dict = {}

        async with self._golf_course_uow:
            for match in matches:
                course_id = self._match_course(match, rounds_by_match)
                if course_id is None:
                    continue
                if course_id not in courses:
                    courses[course_id] = await self._golf_course_uow.golf_courses.find_by_id(
                        course_id
                    )
                course = courses[course_id]
                if course is None:
                    continue

                to_par = self._scorecard_to_par(scorecards.get(match.id, []), course)
                if to_par is not None:
                    results.append(to_par)

        return results

    def _scorecard_to_par(self, hole_scores: list, course) -> int | None:
        """
        Neto respecto al par de una tarjeta entera, o None si le falta un hoyo.

        Un hoyo con `own_score` a None no se rellena ni se ignora: invalida la
        vuelta. En match play es lo normal —te conceden los hoyos que ibas
        ganando y el partido se cierra antes del 18—, así que un partido
        decidido en el 15 no entra en las estadísticas por mucho que esté
        terminado. Es el precio de que la media compare vueltas iguales.
        """
        pars = {hole.number: hole.par for hole in course.holes}
        scored = {
            hole_score.hole_number: hole_score
            for hole_score in hole_scores
            if hole_score.own_score is not None
        }
        if not all(hole_number in scored for hole_number in pars):
            return None

        to_par = 0
        for hole_number, par in pars.items():
            hole_score = scored[hole_number]
            computable = self._calculator.adjusted_gross(
                hole_score.own_score, par, hole_score.strokes_received
            )
            to_par += computable - hole_score.strokes_received - par

        return to_par

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
