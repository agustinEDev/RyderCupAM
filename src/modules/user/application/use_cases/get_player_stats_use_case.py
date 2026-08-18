"""Caso de Uso: resumen de rendimiento de un jugador (BE #128, BE #167)."""

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal

from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.playing_handicap_calculator import TeeRating
from src.modules.competition.domain.services.score_differential_calculator import (
    PlayedRound,
    ScoreDifferentialCalculator,
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
from src.shared.domain.services.countable_round import HALF_ROUND_HOLES, countable_holes

# Tope de partidas que se agregan para la media, por cada fuente. Sin él, una
# cuenta con años de historial cargaría todos sus scores para calcular un único
# número, y en torneo cada partido añade además una consulta de tarjeta.
MAX_ROUNDS_AGGREGATED = 100

# El Score Differential se calcula con el Course Handicap, que es el Playing
# Handicap sin recortar por formato: el allowance reparte ventaja dentro de una
# partida, y el WHS mide la vuelta contra el campo, no contra los rivales.
COURSE_HANDICAP_ALLOWANCE = 100


@dataclass(frozen=True)
class _ComputableRound:
    """
    Una vuelta entera ya reducida a lo que las estadísticas necesitan.

    `played_round` va en None cuando la vuelta no se puede convertir en un
    diferencial (no se sabe desde qué tee se jugó, o sus ratings no son válidos
    para el WHS). Esa vuelta sigue contando para la media y para el total: lo
    único que no puede hacer es decir a qué hándicap se jugó.
    """

    played_on: date_type
    to_par: int
    played_round: PlayedRound | None


class GetPlayerStatsUseCase:
    """
    Agrega el rendimiento de un jugador a partir de los módulos que lo generan.

    Solo cuentan las **vueltas terminadas y sin huecos** de partidas cerradas:
    vale la vuelta entera y valen los nueve de ida o los de vuelta, pero una
    tarjeta a la que le faltan hoyos sueltos queda fuera, tanto de la media como
    del contador de rondas. Media docena de vueltas comparables valen más que
    veinte a medio anotar, y un `rounds_played` que incluyera rondas que no
    entran en la media daría dos números que no cuadran entre sí.

    Media vuelta se lleva a la escala de 18 antes de mezclarla con el resto: sin
    eso, jugar nueve hoyos parecería mejorar el juego.

    Sobre esas mismas vueltas se calculan los **Score Differentials** del WHS
    (BE #167), que dicen a qué hándicap se jugó cada una. Ahí la exigencia es
    mayor: hace falta saber desde qué tee se jugó, porque sin Slope ni Course
    Rating no hay diferencial que calcular.

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
        differential_calculator: ScoreDifferentialCalculator | None = None,
    ):
        self._user_uow = user_uow
        self._competition_uow = competition_uow
        self._quick_match_uow = quick_match_uow
        self._golf_course_uow = golf_course_uow
        self._calculator = stableford_calculator or StablefordCalculator()
        self._differentials = differential_calculator or ScoreDifferentialCalculator()

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

        quick_rounds = await self._collect_quick_match_rounds(user_id, golf_course_id, handicap)

        async with self._competition_uow:
            competition_matches = (
                await self._competition_uow.matches.find_completed_for_player(
                    user_id, limit=MAX_ROUNDS_AGGREGATED
                )
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

        competition_rounds = await self._collect_competition_rounds(
            user_id, competition_matches, rounds_by_match, scorecards, handicap
        )

        # Las dos fuentes llegan ordenadas por su cuenta; el registro del WHS es
        # cronológico y no distingue de dónde salió cada vuelta
        computable_rounds = sorted(
            quick_rounds + competition_rounds, key=lambda item: item.played_on, reverse=True
        )
        differentials = self._differentials.differentials(
            [item.played_round for item in computable_rounds if item.played_round is not None]
        )

        return PlayerStatsResponseDTO(
            handicap=handicap,
            handicap_trend=self._as_float(self._differentials.trend(differentials)),
            scoring_avg=self._average_to_par([item.to_par for item in computable_rounds]),
            rounds_played=len(computable_rounds),
            tournaments_total=tournaments_total,
            tournaments_active=tournaments_active,
            estimated_index=self._as_float(self._differentials.estimated_index(differentials)),
            playing_avg=self._as_float(self._differentials.playing_average(differentials)),
            best_differential=self._as_float(self._differentials.best_differential(differentials)),
            rounds_with_differential=len(differentials),
            # La serie que se publica es la misma ventana que miran el índice y
            # la mejor vuelta: publicar más dejaría que un cliente calculase su
            # propio mínimo sobre vueltas que ninguna otra cifra está contando
            differentials=[
                float(value) for value in self._differentials.scoring_record(differentials)
            ],
        )

    async def _collect_quick_match_rounds(
        self,
        user_id: UserId,
        golf_course_id: GolfCourseId | None,
        profile_handicap: float | None,
    ) -> list[_ComputableRound]:
        """
        Vueltas rápidas computables del jugador.

        Solo entran las partidas terminadas con la tarjeta entera: una vuelta a
        medias no se puede comparar con una completa, y con el campo borrado no
        hay ni pares contra los que medirla.

        `list_for_user` ya descarta las que el propio usuario ocultó (#127), y
        lo hace por participante: una partida que A ocultó sigue contando para
        B. Esa regla se hereda tal cual en lugar de reimplementarse aquí.
        """
        results: list[_ComputableRound] = []

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
                played = self._computable_holes(
                    scores_by_hole, self._hole_card(course, participant)
                )
                if played is None:
                    continue

                holes = [
                    HoleSetup(hole.number, hole.par, hole.stroke_index) for hole in played
                ]
                # Son DOS hándicaps distintos y no se pueden compartir:
                #
                # - La media de la casa usa el hándicap con el que se jugó, y en
                #   una partida scratch no hubo ninguno.
                # - El diferencial WHS de más abajo usa siempre el efectivo,
                #   scratch o no: ahí el hándicap solo sirve para el tope de
                #   doble bogey neto del Adjusted Gross Score, que es parte de
                #   la fórmula WHS y no depende de cómo se jugara la partida.
                effective_handicap = self._effective_handicap(participant, profile_handicap)
                scoring_handicap = effective_handicap if match.uses_handicap() else None
                totals = self._calculator.compute_participant_totals(
                    handicap=scoring_handicap,
                    holes=holes,
                    scores_by_hole=scores_by_hole,
                    allowance_percentage=match.get_effective_allowance(),
                    # La media junta partidas rápidas y torneo: si solo una de
                    # las dos topara los hoyos malos, no serían comparables
                    cap_at_net_double_bogey=True,
                )
                results.append(
                    _ComputableRound(
                        # No hay campo de cuándo se jugó: la partida rápida se
                        # crea el mismo día que se juega
                        played_on=match.created_at.date(),
                        to_par=self._to_eighteen(totals.to_par, len(played)),
                        played_round=self._to_played_round(
                            course=course,
                            holes=holes,
                            scores_by_hole=scores_by_hole,
                            handicap=effective_handicap,
                            tee_color=participant.tee_color,
                            tee_gender=participant.tee_gender,
                        ),
                    )
                )

        return results

    async def _collect_competition_rounds(
        self,
        user_id: UserId,
        matches: list,
        rounds_by_match: dict,
        scorecards: dict,
        profile_handicap: float | None,
    ) -> list[_ComputableRound]:
        """
        Vueltas de torneo computables del jugador.

        El formato del partido da igual: en match play también firmas una
        tarjeta con tus golpes, y esa tarjeta dice a qué nivel jugaste tan bien
        como la de una vuelta de medal. Solo entran las que estén enteras.

        Se usa `own_score`, no el `net_score` de la entidad: ese solo se calcula
        cuando el marcador ha validado el hoyo, así que media tarjeta legítima
        se quedaría fuera por no haberse cerrado la validación cruzada. Los
        golpes recibidos ya vienen resueltos por hoyo desde que se generó el
        partido, sin repartirlos aquí otra vez.
        """
        results: list[_ComputableRound] = []
        courses: dict = {}

        async with self._golf_course_uow:
            for match in matches:
                round_ = rounds_by_match.get(match.id)
                course_id = self._match_course(match, rounds_by_match)
                if round_ is None or course_id is None:
                    continue
                if course_id not in courses:
                    courses[course_id] = await self._golf_course_uow.golf_courses.find_by_id(
                        course_id
                    )
                course = courses[course_id]
                if course is None:
                    continue

                hole_scores = scorecards.get(match.id, [])
                player = self._find_match_player(match, user_id)
                hole_card = self._hole_card(course, player)
                to_par = self._scorecard_to_par(hole_scores, hole_card)
                if to_par is None:
                    continue

                scores_by_hole = {
                    hole_score.hole_number: hole_score.own_score
                    for hole_score in hole_scores
                    if hole_score.own_score is not None
                }
                # El diferencial mide los mismos hoyos que la media, no el campo
                # entero: en media vuelta, los otros nueve no se jugaron
                played = self._computable_holes(scores_by_hole, hole_card) or []
                holes = [
                    HoleSetup(hole.number, hole.par, hole.stroke_index) for hole in played
                ]
                results.append(
                    _ComputableRound(
                        played_on=round_.round_date,
                        to_par=to_par,
                        played_round=self._to_played_round(
                            course=course,
                            holes=holes,
                            scores_by_hole=scores_by_hole,
                            # El partido guardó el hándicap del jugador cuando
                            # se generó: una vuelta de hace meses se mide con el
                            # hándicap que tenía entonces, no con el de hoy
                            handicap=self._match_player_handicap(player, profile_handicap),
                            tee_color=player.tee_color if player else None,
                            tee_gender=player.tee_gender if player else None,
                        ),
                    )
                )

        return results

    # ==================== Diferenciales ====================

    def _to_played_round(
        self,
        course,
        holes: list[HoleSetup],
        scores_by_hole: dict,
        handicap: float | None,
        tee_color,
        tee_gender,
    ) -> PlayedRound | None:
        """
        La vuelta convertida en materia prima para el diferencial, o None.

        El Adjusted Gross Score se recalcula con el Course Handicap en lugar de
        reaprovechar el de la media: son dos topes distintos a propósito. La
        media es una métrica de la casa y usa el hándicap con el que se jugó la
        partida; el diferencial pretende ser WHS y el WHS ignora el allowance.
        """
        tee_rating = self._tee_rating(course, tee_color, tee_gender)
        if tee_rating is None:
            return None

        totals = self._calculator.compute_participant_totals(
            handicap=handicap,
            holes=holes,
            scores_by_hole=scores_by_hole,
            tee_rating=tee_rating,
            allowance_percentage=COURSE_HANDICAP_ALLOWANCE,
            cap_at_net_double_bogey=True,
        )
        # Media vuelta se lleva a 18 duplicando los golpes ajustados, y se mide
        # contra el rating de 18 tal cual. Es lo mismo que medir los nueve
        # contra la mitad del rating y luego doblar el diferencial —
        # `2 x (113/S) x (AGS9 - CR/2)` es `(113/S) x (2·AGS9 - CR)`— pero sin
        # construir un `TeeRating` con un CR de 35.9 y un par de 36, que su
        # propia validación rechaza por estar fuera de los límites del WHS.
        # La aproximación está en dar por hecho que los nueve jugados valen la
        # mitad del campo; sin ratings de nueve hoyos no hay forma de afinarlo.
        return PlayedRound(
            adjusted_gross_score=self._to_eighteen(totals.adjusted_gross_strokes, len(holes)),
            tee_rating=tee_rating,
        )

    @staticmethod
    def _tee_rating(course, tee_color, tee_gender) -> TeeRating | None:
        """
        Ratings del tee que se jugó, o None si no se puede saber.

        El tee se identifica por categoría y género, que es su clave única en el
        campo: los tees no tienen id propio. El par no vive en el tee, sale de
        sumar los hoyos.

        Un tee cuyos ratings no entran en los límites del WHS devuelve None en
        lugar de propagar el error: el catálogo de campos admite un rango de
        Course Rating más ancho que el que el sistema acepta para calcular, y
        una estadística no es motivo para tumbar la respuesta entera.
        """
        if tee_color is None:
            return None

        tee = next(
            (
                candidate
                for candidate in course.tees
                if candidate.color == tee_color and candidate.gender == tee_gender
            ),
            None,
        )
        if tee is None:
            return None

        course_rating = Decimal(str(tee.course_rating))
        course_par = sum(hole.par for hole in course.reference_card)
        try:
            return TeeRating(
                course_rating=course_rating,
                slope_rating=tee.slope_rating,
                # El par es el de la barra: entra en el Course Handicap como
                # (CR - Par), así que con la tarjeta de referencia el jugador de
                # otra barra sale con una base de golpes que no es la suya, y
                # con ella el tope de doble bogey neto y el diferencial.
                par=tee.par_total if tee.holes else course_par,
            )
        except (ValueError, TypeError):
            # Una barra con el par fuera del rango WHS es un dato suelto del
            # importador, no una vuelta que no se jugó: se valora contra el par
            # del campo en vez de perder la vuelta y con ella el diferencial.
            # Mismo criterio que `TeeContextBuilder._rating_for`.
            try:
                return TeeRating(
                    course_rating=course_rating,
                    slope_rating=tee.slope_rating,
                    par=course_par,
                )
            except (ValueError, TypeError):
                return None

    # ==================== Lectura de tarjetas ====================

    @staticmethod
    def _computable_holes(scores_by_hole: dict, hole_card: list) -> list | None:
        """
        Los hoyos que forman una vuelta computable, o None si no forman ninguna.

        La regla vive en `shared` porque el feed de logros (BE #175) tiene que
        aplicar exactamente la misma: una tarjeta que no vale para la media
        tampoco vale para presumir.
        """
        return countable_holes(scores_by_hole, hole_card)

    @staticmethod
    def _to_eighteen(value: int, holes_played: int) -> int:
        """
        Lleva a la escala de 18 lo que se jugó en media vuelta.

        Sin esto, mezclar un +3 de nueve hoyos con un +6 de dieciocho daría una
        media que no significa nada, y jugar medias vueltas parecería mejorar el
        juego. Duplicar es una aproximación —los nueve de ida y los de vuelta no
        tienen por qué ser igual de difíciles—, pero es la que mantiene todas
        las vueltas hablando en la misma escala.
        """
        return value * 2 if holes_played == HALF_ROUND_HOLES else value

    async def _rounds_by_match(self, matches: list) -> dict:
        """
        La ronda de cada partido, una consulta por ronda distinta.

        Hace falta para tres cosas que el partido no sabe por sí solo: en qué
        campo se jugó, con qué pares se compara su tarjeta y qué día fue.
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

    def _scorecard_to_par(self, hole_scores: list, hole_card: list) -> int | None:
        """
        Neto respecto al par de la tarjeta, o None si no forma una vuelta.

        Un hoyo con `own_score` a None no se rellena ni se ignora: invalida la
        vuelta. Lo que decide es la tarjeta, no en qué hoyo se ganó el partido:
        un match play resuelto en el 15 cuenta igual que cualquier otra vuelta
        si los jugadores siguieron anotando hasta el 18. Lo que deja la ronda
        fuera es dejar de anotar, no cerrar pronto.
        """
        scored = {
            hole_score.hole_number: hole_score
            for hole_score in hole_scores
            if hole_score.own_score is not None
        }
        played = self._computable_holes(scored, hole_card)
        if played is None:
            return None

        to_par = 0
        for hole in played:
            hole_score = scored[hole.number]
            computable = self._calculator.adjusted_gross(
                hole_score.own_score, hole.par, hole_score.strokes_received
            )
            to_par += computable - hole_score.strokes_received - hole.par

        return self._to_eighteen(to_par, len(played))

    # ==================== Jugadores y hándicaps ====================

    @staticmethod
    def _hole_card(course, player) -> list:
        """
        Tarjeta de la barra que juega ese jugador.

        El par y el índice son de la barra: puntuar con la tarjeta de referencia
        del campo mide a quien no juega la primera contra un par que no es el
        suyo. Sin campo o sin barra elegida cae a la de referencia, que es lo
        único que hay.
        """
        if course is None:
            return []
        if player is None:
            # El jugador puede no aparecer en el partido; el resto del cálculo
            # ya lo contempla y sigue con lo que haya.
            return course.reference_card
        return course.hole_card_for(player.tee_color, player.tee_gender)

    @staticmethod
    def _find_participant(match, user_id: UserId):
        return next(
            (p for p in match.participants if p.user_id is not None and p.user_id == user_id),
            None,
        )

    @staticmethod
    def _find_match_player(match, user_id: UserId):
        """El jugador dentro del partido, mire en el equipo que mire."""
        return match.find_player(user_id)

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
    def _match_player_handicap(player, profile_handicap: float | None) -> float | None:
        """
        Hándicap del jugador en ese partido de torneo.

        `MatchPlayer.player_handicap` es una foto del hándicap en el momento de
        generar el partido, que es exactamente lo que el WHS quiere para medir
        una vuelta antigua. Cuando falta, no queda más que el del perfil.
        """
        if player is not None and player.player_handicap is not None:
            return float(player.player_handicap)
        return profile_handicap

    # ==================== Agregación ====================

    @staticmethod
    def _average_to_par(rounds_to_par: list[int]) -> float | None:
        """None sin rondas: no hay media que dar, que no es una media de cero."""
        if not rounds_to_par:
            return None
        return round(sum(rounds_to_par) / len(rounds_to_par), 1)

    @staticmethod
    def _as_float(value: Decimal | None) -> float | None:
        return float(value) if value is not None else None
