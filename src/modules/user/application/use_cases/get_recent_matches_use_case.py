"""Caso de Uso: historial reciente de partidas de un jugador (BE #128)."""

from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import Decimal

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.services.stroke_context_builder import (
    StrokeContextBuilder,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.hole_completion_service import (
    hole_is_complete,
)
from src.modules.quick_match.domain.services.stableford_calculator import (
    NET_DOUBLE_BOGEY_OVER_PAR,
    HoleSetup,
    StablefordCalculator,
)
from src.modules.quick_match.domain.services.stroke_allocation_service import (
    StrokeAllocationService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.quick_match.domain.value_objects.scoring_format import ScoringFormat
from src.modules.user.application.dto.player_stats_dto import (
    RecentMatchDTO,
    RecentMatchesResponseDTO,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

DEFAULT_LIMIT = 10

# `GolfCourse` valida exactamente 18 hoyos como invariante, así que recorrer el
# rango fijo equivale a recorrer los hoyos del campo. Si algún día se admiten
# campos de nueve, hay que iterar los hoyos anotados en lugar de este rango.
TOTAL_HOLES = 18

# Cómo queda el partido para quien pregunta, no para el equipo A
RESULT_WON = "WON"
RESULT_LOST = "LOST"
RESULT_HALVED = "HALVED"
HALVED_WINNER = "HALVED"


@dataclass
class _QuickMatchRaw:
    """Lo leído de una partida rápida antes de resolver nombres y campo."""

    match: QuickMatch
    participant: QuickMatchParticipant
    scores_by_participant: dict = field(default_factory=dict)


@dataclass
class _CompetitionMatchRaw:
    """Lo leído de un partido de torneo antes de resolver nombres y campo."""

    match: Match
    round_: Round
    tournament_name: str | None
    # La tarjeta del jugador, para poder dar sus golpes y sus puntos: el
    # partido guarda quién ganó, no cómo jugó cada uno
    hole_scores: list


class GetRecentMatchesUseCase:
    """
    Historial de partidas del jugador, unificando torneo y partida rápida.

    Son dos cosas distintas puestas en una misma lista: un partido de torneo se
    juega por hoyos contra un rival y termina en "3&2"; una partida rápida libre
    se juega contra el par y termina en "+4" o en puntos Stableford. El DTO deja
    en `None` lo que no aplica a cada una en lugar de inventar equivalencias.

    Cada fuente se lee en su propia unidad de trabajo y solo después se resuelven
    nombres de jugadores y campos, en bloque: así una lista de diez partidas no
    dispara una consulta por participante.
    """

    def __init__(
        self,
        user_uow: UserUnitOfWorkInterface,
        competition_uow: CompetitionUnitOfWorkInterface,
        quick_match_uow: QuickMatchUnitOfWorkInterface,
        golf_course_uow: GolfCourseUnitOfWorkInterface,
        stableford_calculator: StablefordCalculator | None = None,
        scoring_service: ScoringService | None = None,
        stroke_allocation_service: StrokeAllocationService | None = None,
    ):
        self._user_uow = user_uow
        self._competition_uow = competition_uow
        self._quick_match_uow = quick_match_uow
        self._golf_course_uow = golf_course_uow
        self._calculator = stableford_calculator or StablefordCalculator()
        self._scoring_service = scoring_service or ScoringService()
        self._stroke_allocation_service = (
            stroke_allocation_service or StrokeAllocationService()
        )

    async def execute(
        self, user_id: UserId, limit: int = DEFAULT_LIMIT
    ) -> RecentMatchesResponseDTO:
        """
        Últimas `limit` partidas del jugador, de la más reciente a la más antigua.

        Se piden `limit` de cada fuente y se recorta después de mezclarlas: no se
        sabe de qué lado caen las más recientes hasta tenerlas todas.
        """
        quick_raws = await self._read_quick_matches(user_id, limit)
        competition_raws = await self._read_competition_matches(user_id, limit)

        users_by_id = await self._load_users(user_id, quick_raws, competition_raws)
        courses_by_id = await self._load_golf_courses(quick_raws, competition_raws)

        player = users_by_id.get(user_id)
        profile_handicap = float(player.handicap.value) if player and player.handicap else None

        entries = [
            self._to_quick_match_dto(raw, users_by_id, courses_by_id, profile_handicap, user_id)
            for raw in quick_raws
        ] + [
            self._to_competition_match_dto(raw, user_id, users_by_id, courses_by_id)
            for raw in competition_raws
        ]

        # Una partida sin fecha resoluble se va al final en lugar de romper el orden
        entries.sort(key=lambda entry: entry.date or date_type.min, reverse=True)
        return RecentMatchesResponseDTO(matches=entries[:limit])

    # ==================== Lectura ====================

    async def _read_quick_matches(self, user_id: UserId, limit: int) -> list[_QuickMatchRaw]:
        """
        Partidas rápidas terminadas del jugador, con sus scores.

        `list_for_user` ya descarta las que este jugador ocultó (#127), y solo
        para él: una partida que A ocultó sigue en el historial de B.

        Aquí NO se usa `list_for_stats`, al revés que el resumen: esta lista es
        el historial y tiene que enseñar también las que el jugador dejó fuera
        de sus estadísticas (BE #242). Viajan con `excluded_from_stats` puesto
        para que la pantalla las marque; si no, el resumen diría cero vueltas
        mientras justo debajo se lista una, sin nada que explique la diferencia.
        """
        raws: list[_QuickMatchRaw] = []

        async with self._quick_match_uow:
            matches = await self._quick_match_uow.quick_matches.list_for_user(
                user_id, status=QuickMatchStatus.COMPLETED, limit=limit
            )

            for match in matches:
                participant = self._find_participant(match, user_id)
                if participant is None:
                    continue

                hole_scores = await self._quick_match_uow.quick_match_hole_scores.find_by_match(
                    match.id
                )
                scores_by_participant: dict = {}
                for hole_score in hole_scores:
                    scores_by_participant.setdefault(hole_score.participant_id, {})[
                        hole_score.hole_number
                    ] = hole_score.score

                raws.append(
                    _QuickMatchRaw(
                        match=match,
                        participant=participant,
                        scores_by_participant=scores_by_participant,
                    )
                )

        return raws

    async def _read_competition_matches(
        self, user_id: UserId, limit: int
    ) -> list[_CompetitionMatchRaw]:
        """
        Partidos de torneo terminados del jugador, con su ronda y su torneo.

        La fecha y el campo viven en la ronda, y el nombre del torneo en la
        competición: un partido por sí solo no sabe cuándo ni dónde se jugó.
        """
        raws: list[_CompetitionMatchRaw] = []
        rounds_cache: dict = {}
        competition_names: dict = {}

        async with self._competition_uow:
            matches = await self._competition_uow.matches.find_completed_for_player(
                user_id, limit=limit
            )

            for match in matches:
                if match.round_id not in rounds_cache:
                    rounds_cache[match.round_id] = await self._competition_uow.rounds.find_by_id(
                        match.round_id
                    )
                round_ = rounds_cache[match.round_id]
                if round_ is None:
                    continue

                if round_.competition_id not in competition_names:
                    competition = await self._competition_uow.competitions.find_by_id(
                        round_.competition_id
                    )
                    competition_names[round_.competition_id] = (
                        competition.name.value if competition else None
                    )

                raws.append(
                    _CompetitionMatchRaw(
                        match=match,
                        round_=round_,
                        tournament_name=competition_names[round_.competition_id],
                        hole_scores=await self._competition_uow.hole_scores.find_by_match_and_player(
                            match.id, user_id
                        ),
                    )
                )

        return raws

    async def _load_users(
        self,
        user_id: UserId,
        quick_raws: list[_QuickMatchRaw],
        competition_raws: list[_CompetitionMatchRaw],
    ) -> dict[UserId, User]:
        """Todos los jugadores que aparecen en el historial, en una sola consulta."""
        user_ids = {user_id}
        for quick_raw in quick_raws:
            user_ids.update(
                p.user_id for p in quick_raw.match.participants if p.user_id is not None
            )
        for competition_raw in competition_raws:
            user_ids.update(
                player.user_id
                for player in (
                    *competition_raw.match.team_a_players,
                    *competition_raw.match.team_b_players,
                )
            )

        async with self._user_uow:
            users = await self._user_uow.users.find_by_ids(list(user_ids))
        return {user.id: user for user in users if user.id is not None}

    async def _load_golf_courses(
        self,
        quick_raws: list[_QuickMatchRaw],
        competition_raws: list[_CompetitionMatchRaw],
    ) -> dict[GolfCourseId, GolfCourse]:
        """Campos jugados, uno por id distinto y no uno por partida."""
        course_ids = {raw.match.golf_course_id for raw in quick_raws}
        course_ids.update(raw.round_.golf_course_id for raw in competition_raws)

        courses: dict[GolfCourseId, GolfCourse] = {}
        async with self._golf_course_uow:
            for course_id in course_ids:
                course = await self._golf_course_uow.golf_courses.find_by_id(course_id)
                if course is not None:
                    courses[course_id] = course
        return courses

    # ==================== Mapeo ====================

    def _to_quick_match_dto(
        self,
        raw: _QuickMatchRaw,
        users_by_id: dict[UserId, User],
        courses_by_id: dict[GolfCourseId, GolfCourse],
        profile_handicap: float | None,
        user_id: UserId,
    ) -> RecentMatchDTO:
        match = raw.match
        course = courses_by_id.get(match.golf_course_id)
        partners, opponents = self._quick_match_rivals(match, raw.participant, users_by_id)

        result = None
        score = None

        # Los totales se calculan siempre, sea cual sea el formato: los puntos
        # Stableford son la única cifra que compara vueltas entre sí, porque 36
        # puntos es jugar a tu hándicap en cualquier campo y cualquier formato
        totals = self._participant_totals(raw, course, profile_handicap)
        # En foursomes no hay vuelta propia que enseñar —la pareja juega una
        # bola— pero sí los golpes brutos del bando, y los mismos para los dos.
        # Leyendo solo lo anotado a nombre de cada uno, el que llevaba la fila
        # salía con una vuelta entera de 72 golpes y su compañero sin nada.
        side_strokes = (
            self._foursomes_side_strokes(raw, course)
            if raw.match.match_format == MatchFormat.FOURSOMES
            else None
        )

        if match.match_format is not None:
            result, score = self._quick_match_play_outcome(raw, course, users_by_id)
        elif totals is not None:
            if match.scoring_format == ScoringFormat.STABLEFORD:
                score = f"{totals.stableford_points} pts"
            else:
                score = self._calculator.format_to_par(totals.to_par)

        return RecentMatchDTO(
            id=str(match.id.value),
            excluded_from_stats=match.is_stats_excluded_for(ParticipantId(user_id.value)),
            # Una partida rápida no guarda cuándo se jugó, solo cuándo se creó:
            # se juegan del tirón, así que la fecha de creación es la del juego
            date=match.created_at.date(),
            match_format=match.match_format.value if match.match_format else None,
            scoring_format=match.scoring_format.value if match.scoring_format else None,
            golf_course_id=str(match.golf_course_id.value),
            golf_course_name=course.name if course else None,
            tournament_name=None,
            result=result,
            score=score,
            stableford_points=None if side_strokes else (
                totals.stableford_points if totals else None
            ),
            total_strokes=side_strokes[0] if side_strokes else (
                totals.total_strokes if totals else None
            ),
            holes_played=side_strokes[1] if side_strokes else (
                totals.holes_played if totals else None
            ),
            partners=partners,
            opponents=opponents,
        )

    def _to_competition_match_dto(
        self,
        raw: _CompetitionMatchRaw,
        user_id: UserId,
        users_by_id: dict[UserId, User],
        courses_by_id: dict[GolfCourseId, GolfCourse],
    ) -> RecentMatchDTO:
        match = raw.match
        course = courses_by_id.get(raw.round_.golf_course_id)

        in_team_a = any(player.user_id == user_id for player in match.team_a_players)
        own_team, rival_team = (
            (match.team_a_players, match.team_b_players)
            if in_team_a
            else (match.team_b_players, match.team_a_players)
        )
        partners = [
            self._user_name(player.user_id, users_by_id)
            for player in own_team
            if player.user_id != user_id
        ]
        opponents = [self._user_name(player.user_id, users_by_id) for player in rival_team]
        # El par y el indice son de la barra de quien juega, no del campo
        own_player = match.find_player(user_id)
        hole_card = (
            []
            if course is None
            else course.hole_card_for(own_player.tee_color, own_player.tee_gender)
            if own_player is not None
            else course.reference_card
        )
        total_strokes, holes_played, points = self._scorecard_totals(raw, hole_card)
        # En foursomes la pareja juega UNA bola, así que la tarjeta no es la
        # vuelta de ninguno de los dos por separado y no lleva puntos Stableford.
        # Los golpes del bando sí se enseñan, y son los mismos para los dos
        # compañeros. Es la misma regla que en partida rápida, donde vive en
        # `_to_quick_match_dto`: aquí se había quedado sin aplicar.
        is_foursomes = raw.round_.match_format == MatchFormat.FOURSOMES

        return RecentMatchDTO(
            id=str(match.id.value),
            date=raw.round_.round_date,
            match_format=raw.round_.match_format.value,
            # Un partido de torneo se juega siempre por hoyos: el eje MEDAL /
            # STABLEFORD es de las partidas rápidas y aquí no aplica
            scoring_format=None,
            golf_course_id=str(raw.round_.golf_course_id.value),
            golf_course_name=course.name if course else None,
            tournament_name=raw.tournament_name,
            result=self._result_for_team(match.get_winner(), "A" if in_team_a else "B"),
            score=match.result.get("score") if match.result else None,
            stableford_points=None if is_foursomes else points,
            total_strokes=total_strokes,
            holes_played=holes_played,
            partners=partners,
            opponents=opponents,
        )

    # ==================== Cálculo ====================

    def _quick_match_strokes(
        self,
        raw: _QuickMatchRaw,
        course: GolfCourse | None,
        users_by_id: dict[UserId, User],
    ) -> dict:
        """
        Reparto de golpes de una partida rápida del historial.

        Sin el campo (borrado, o no cargado) se devuelve un reparto vacío: el
        resultado sale a bruto, que es peor que nada pero mejor que no poder
        mostrar el historial.
        """
        if course is None:
            return {}

        context = StrokeContextBuilder.build(course)
        handicaps = {}
        for participant in raw.match.participants:
            if participant.is_guest:
                value = participant.handicap
            elif participant.custom_handicap is not None:
                value = participant.custom_handicap
            else:
                user = users_by_id.get(participant.user_id)
                value = user.handicap.value if user and user.handicap else None
            handicaps[participant.participant_id] = None if value is None else Decimal(str(value))

        return self._stroke_allocation_service.allocate(
            participants=raw.match.participants,
            handicaps=handicaps,
            tee_ratings=context.tee_ratings,
            holes_by_stroke_index=context.holes_by_stroke_index,
            holes_by_stroke_index_by_tee=context.holes_by_stroke_index_by_tee,
            match_format=raw.match.match_format,
            allowance_percentage=raw.match.get_effective_allowance(),
            play_mode=raw.match.play_mode,
        )

    def _quick_match_play_outcome(
        self,
        raw: _QuickMatchRaw,
        course: GolfCourse | None,
        users_by_id: dict[UserId, User],
    ) -> tuple[str | None, str | None]:
        """
        Cómo quedó una partida rápida por equipos, desde el lado del jugador.

        El resultado no está guardado en ningún sitio: se recalcula hoyo a hoyo
        con el mismo motor que usa el detalle de la partida. Solo cuentan los
        hoyos donde anotaron los dos bandos, porque un hoyo a medias no se puede
        adjudicar, y con la misma regla que el detalle —`hole_is_complete`— y no
        con una copia: escrita aquí a mano, exigía los cuatro scores y dejaba el
        historial sin resultado en todas las partidas de foursomes mientras la
        partida abierta ya las puntuaba.

        Los golpes se reparten con el mismo servicio que el detalle: si aquí se
        compararan los brutos, el historial contaría una película distinta de la
        que muestra la partida abierta.
        """
        rosters = raw.match.team_rosters()
        if rosters is None:
            return None, None
        team_a_ids, team_b_ids = rosters

        strokes_by_participant = self._quick_match_strokes(raw, course, users_by_id)

        hole_results = []
        for hole_number in range(1, TOTAL_HOLES + 1):
            scores = {
                participant_id: holes[hole_number]
                for participant_id, holes in raw.scores_by_participant.items()
                if hole_number in holes
            }
            if not hole_is_complete(
                scores, team_a_ids, team_b_ids, raw.match.match_format
            ):
                continue

            def net(pid, hole=hole_number, values=scores):
                # La raya (score nulo) se propaga: `calculate_hole_winner` la lee
                # como bando que no entrego bola y le da el hoyo al rival, que es
                # la regla de match play. Convertirla en un numero aqui la haria
                # competir por el hoyo.
                if values[pid] is None:
                    return None
                allocation = strokes_by_participant.get(pid)
                if allocation is None:
                    return values[pid]
                return allocation.net_score(hole, values[pid])

            # Solo los que anotaron: en foursomes el bando entrega UNA bola, asi
            # que el companero no tiene score y `values[pid]` reventaria.
            hole_results.append(
                self._scoring_service.calculate_hole_winner(
                    [net(pid) for pid in team_a_ids if pid in scores],
                    [net(pid) for pid in team_b_ids if pid in scores],
                    raw.match.match_format,
                )
            )

        if not hole_results:
            return None, None

        own_team = "A" if raw.participant.participant_id in team_a_ids else "B"
        standing = self._scoring_service.calculate_match_standing(hole_results)

        if self._scoring_service.is_match_decided(standing):
            # Se cerró antes del 18: el resultado va en "3&2", ventaja y hoyos
            # que quedaban
            outcome = self._scoring_service.format_decided_result(hole_results)
            return self._result_for_team(outcome["winner"], own_team), outcome["score"]

        if standing["leading_team"] is None:
            return RESULT_HALVED, "AS"

        # Terminado sin decidirse antes de tiempo: la ventaja tal cual ("2UP").
        # No vale `format_decided_result` aquí: inventaría un "2&7" con los hoyos
        # que quedaban sin anotar, como si el partido se hubiera cerrado en ellos
        return (
            self._result_for_team(standing["leading_team"], own_team),
            standing["status"],
        )

    def _foursomes_side_strokes(
        self, raw: _QuickMatchRaw, course: GolfCourse | None
    ) -> tuple[int, int] | None:
        """
        Golpes brutos y hoyos del BANDO en foursomes: una bola por hoyo.

        Normalmente hay una sola: el frontend guarda la bola a nombre del primer
        jugador del bando, la anote quien la anote. Si llegan dos se toma la
        MENOR, que es la que usa `ScoringService._best_ball` para adjudicar el
        hoyo: contar aquí una y adjudicar con la otra dejaría la partida con
        unos golpes que no explican su resultado. Lo que nunca se hace es
        sumarlas, porque comparten bola y eso doblaría la vuelta.

        Un hoyo RECOGIDO cuenta: está jugado, y lo decide el resultado del
        partido igual que cualquier otro. Vale doble bogey BRUTO —`par + 2`, sin
        golpes recibidos—, porque esta cifra es bruta y meterle un hoyo neto
        dentro mezclaría dos escalas en el mismo número. Dejarlo fuera daba un
        total de menos hoyos de los que el partido dice que se jugaron.

        Devuelve None si no hay bandos resolubles o el bando no anotó nada.
        """
        rosters = raw.match.team_rosters()
        if rosters is None:
            return None

        team_a_ids, team_b_ids = rosters
        my_side = team_a_ids if raw.participant.participant_id in team_a_ids else team_b_ids
        side_in_order = [
            p.participant_id for p in raw.match.participants if p.participant_id in my_side
        ]
        par_by_hole = self._side_pars(raw, course, side_in_order)

        total_strokes = 0
        holes_played = 0
        for hole_number in range(1, TOTAL_HOLES + 1):
            # La CLAVE, no el valor: la raya está presente con valor None y es un
            # hoyo jugado, mientras que un hoyo sin anotar no tiene entrada.
            anotaciones = [
                raw.scores_by_participant[participant_id][hole_number]
                for participant_id in side_in_order
                if hole_number in raw.scores_by_participant.get(participant_id, {})
            ]
            if not anotaciones:
                continue

            # El menor de los números, que es lo que hace `ScoringService._best_ball`
            # al decidir el hoyo. Normalmente solo hay uno —la bola se guarda a
            # nombre del primero del bando—, pero si llegan dos que no coinciden,
            # contar aquí uno y adjudicar el hoyo con el otro dejaría la misma
            # partida con unos golpes que no explican su resultado.
            numeros = [score for score in anotaciones if score is not None]
            if numeros:
                total_strokes += min(numeros)
                holes_played += 1
                continue

            # Solo rayas: el bando recogió. Sin el par del hoyo no hay con qué
            # contarlo, y antes que inventar un número se deja fuera.
            par = par_by_hole.get(hole_number)
            if par is None:
                continue
            total_strokes += par + NET_DOUBLE_BOGEY_OVER_PAR
            holes_played += 1

        return (total_strokes, holes_played) if holes_played else None

    @staticmethod
    def _side_pars(
        raw: _QuickMatchRaw, course: GolfCourse | None, side_in_order: list
    ) -> dict[int, int]:
        """
        El par de cada hoyo para la barra del bando, o vacío si no se sabe.

        La barra es la del primer jugador del bando, que es a cuyo nombre se
        guarda la bola: el par sale de SU tarjeta, no del campo, porque en 25 de
        los 800 campos federados cambia entre barras.
        """
        if course is None or not side_in_order:
            return {}

        titular = next(
            (p for p in raw.match.participants if p.participant_id == side_in_order[0]), None
        )
        if titular is None:
            return {}

        return {
            hole.number: hole.par
            for hole in course.hole_card_for(titular.tee_color, titular.tee_gender)
        }

    def _participant_totals(
        self,
        raw: _QuickMatchRaw,
        course: GolfCourse | None,
        profile_handicap: float | None,
    ):
        """Puntos y golpes del jugador en una partida libre; None si no hay con qué."""
        if course is None:
            return None

        scores_by_hole = raw.scores_by_participant.get(raw.participant.participant_id)
        if not scores_by_hole:
            return None

        holes = [
            HoleSetup(hole.number, hole.par, hole.stroke_index)
            for hole in course.hole_card_for(
                raw.participant.tee_color, raw.participant.tee_gender
            )
        ]
        # En una partida scratch nadie recibe golpes, tampoco para los puntos
        # Stableford ni el resultado contra el par: sin esto, una vuelta jugada a
        # bruto se apuntaba como si le hubieran dado golpes.
        handicap = (
            self._effective_handicap(raw.participant, profile_handicap)
            if raw.match.uses_handicap()
            else None
        )
        return self._calculator.compute_participant_totals(
            handicap=handicap,
            holes=holes,
            scores_by_hole=scores_by_hole,
            allowance_percentage=raw.match.get_effective_allowance(),
        )

    def _scorecard_totals(self, raw: _CompetitionMatchRaw, hole_card: list) -> tuple:
        """
        Golpes, hoyos y puntos Stableford de una tarjeta de torneo.

        Los golpes recibidos ya vienen resueltos por hoyo desde que se generó el
        partido, así que no hay que repartirlos otra vez. Se usa `own_score` y
        no `net_score` porque este último solo existe cuando el marcador validó
        el hoyo, y una tarjeta legítima sin validar cerrar se quedaría sin
        cifras que enseñar.
        """
        if not hole_card:
            return None, None, None

        pars = {hole.number: hole.par for hole in hole_card}
        scored = [
            hole_score
            for hole_score in raw.hole_scores
            if hole_score.own_score is not None and hole_score.hole_number in pars
        ]
        if not scored:
            return None, None, None

        total_strokes = sum(hole_score.own_score for hole_score in scored)
        points = sum(
            self._calculator.hole_points(
                hole_score.own_score,
                pars[hole_score.hole_number],
                hole_score.strokes_received,
            )
            for hole_score in scored
        )
        return total_strokes, len(scored), points

    def _quick_match_rivals(
        self,
        match: QuickMatch,
        participant: QuickMatchParticipant,
        users_by_id: dict[UserId, User],
    ) -> tuple[list[str], list[str]]:
        """
        Con quién jugó y contra quién.

        En partido libre no hay bandos: se juega la clasificación individual, de
        modo que los demás son rivales y no compañeros.
        """
        others = [p for p in match.participants if p.participant_id != participant.participant_id]
        if match.match_format is None:
            return [], [self._participant_name(p, users_by_id) for p in others]

        rosters = match.team_rosters()
        if rosters is None:
            return [], [self._participant_name(p, users_by_id) for p in others]
        team_a_ids, _ = rosters

        in_team_a = participant.participant_id in team_a_ids
        partners: list[str] = []
        opponents: list[str] = []
        for other in others:
            same_team = (other.participant_id in team_a_ids) == in_team_a
            (partners if same_team else opponents).append(
                self._participant_name(other, users_by_id)
            )
        return partners, opponents

    # ==================== Helpers ====================

    @staticmethod
    def _result_for_team(winner: str | None, own_team: str) -> str | None:
        """Traduce el ganador del partido ("A"/"B"/"HALVED") al lado del jugador."""
        if winner is None:
            return None
        if winner == HALVED_WINNER:
            return RESULT_HALVED
        return RESULT_WON if winner == own_team else RESULT_LOST

    @staticmethod
    def _find_participant(match: QuickMatch, user_id: UserId) -> QuickMatchParticipant | None:
        return next(
            (p for p in match.participants if p.user_id is not None and p.user_id == user_id),
            None,
        )

    @staticmethod
    def _user_name(user_id: UserId, users_by_id: dict[UserId, User]) -> str:
        user = users_by_id.get(user_id)
        return f"{user.first_name} {user.last_name}" if user else "Unknown"

    @classmethod
    def _participant_name(
        cls, participant: QuickMatchParticipant, users_by_id: dict[UserId, User]
    ) -> str:
        """Un invitado trae su nombre dentro de la partida; un registrado, en su perfil."""
        if participant.is_guest:
            return f"{participant.first_name} {participant.last_name}"
        return cls._user_name(participant.user_id, users_by_id)

    @staticmethod
    def _effective_handicap(
        participant: QuickMatchParticipant, profile_handicap: float | None
    ) -> float | None:
        """Override manual del creador si lo hay, y si no el hándicap del perfil."""
        if participant.custom_handicap is not None:
            return participant.custom_handicap
        return profile_handicap
