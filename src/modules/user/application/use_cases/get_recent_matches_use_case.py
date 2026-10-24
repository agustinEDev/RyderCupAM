"""Caso de Uso: historial reciente de partidas de un jugador (BE #128)."""

from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import Decimal

from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.services.course_context import own_playing_handicap
from src.modules.quick_match.application.services.match_play_result import (
    match_play_result,
    quick_match_strokes,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.stroke_allocation_service import (
    ParticipantStrokes,
    StrokeAllocationService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.user.application.dto.player_stats_dto import (
    RecentMatchDTO,
    RecentMatchesResponseDTO,
)
from src.modules.user.application.services.tournament_round import (
    is_scratch,
    tournament_personal_handicap,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.domain.services.stroke_play_scoring import (
    HoleSetup,
    StrokePlayScoring,
)
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.scoring_format import ScoringFormat

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
    # Una competición scratch: la vuelta propia va sin golpes (BE #517)
    scratch: bool = False


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
        stroke_play_scoring: StrokePlayScoring | None = None,
        scoring_service: MatchPlayScoring | None = None,
        stroke_allocation_service: StrokeAllocationService | None = None,
    ):
        self._user_uow = user_uow
        self._competition_uow = competition_uow
        self._quick_match_uow = quick_match_uow
        self._golf_course_uow = golf_course_uow
        self._calculator = stroke_play_scoring or StrokePlayScoring()
        self._scoring_service = scoring_service or MatchPlayScoring()
        self._stroke_allocation_service = stroke_allocation_service or StrokeAllocationService()

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
        scratch_competitions: set = set()

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
                    if is_scratch(competition):
                        scratch_competitions.add(round_.competition_id)

                raws.append(
                    _CompetitionMatchRaw(
                        match=match,
                        round_=round_,
                        tournament_name=competition_names[round_.competition_id],
                        scratch=round_.competition_id in scratch_competitions,
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
        # El reparto del partido, una vez: lo usan el resultado y la raya del
        # bando en foursomes
        strokes = (
            self._quick_match_strokes(raw, course, users_by_id)
            if match.match_format is not None
            else {}
        )
        # En foursomes no hay vuelta propia que enseñar —la pareja juega una
        # bola— pero sí los golpes brutos del bando, y los mismos para los dos.
        # Leyendo solo lo anotado a nombre de cada uno, el que llevaba la fila
        # salía con una vuelta entera de 72 golpes y su compañero sin nada.
        side_strokes = (
            self._foursomes_side_strokes(raw, course, strokes)
            if raw.match.match_format == MatchFormat.FOURSOMES
            else None
        )

        if match.match_format is not None:
            result, score = self._quick_match_play_outcome(raw, strokes)
        elif totals is not None:
            if match.scoring_format == ScoringFormat.STABLEFORD:
                score = f"{totals.stableford_points} pts"
            else:
                score = self._calculator.format_to_par(totals.to_par)

        return RecentMatchDTO(
            id=str(match.id.value),
            excluded_from_stats=match.is_stats_excluded_for(ParticipantId(user_id.value)),
            date=match.played_at.date(),
            match_format=match.match_format.value if match.match_format else None,
            scoring_format=match.scoring_format.value if match.scoring_format else None,
            golf_course_id=str(match.golf_course_id.value),
            golf_course_name=course.name if course else None,
            # Lo que el jugador le puso al crearla, que es como reconoce la
            # partida después. Es opcional: sin nombre viaja nulo y el cliente
            # decide con qué titular la fila (BE #261)
            match_name=match.name,
            tournament_name=None,
            result=result,
            score=score,
            stableford_points=None
            if side_strokes
            else (totals.stableford_points if totals else None),
            total_strokes=side_strokes[0]
            if side_strokes
            else (totals.total_strokes if totals else None),
            holes_played=side_strokes[1]
            if side_strokes
            else (totals.holes_played if totals else None),
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
        # Los puntos de su vuelta propia, como en partida rápida: con su índice
        # (el que guardó el partido, o el del perfil) en su barra al 100 %, no
        # con la diferencia con el rival que reparte el partido (BE #517)
        user = users_by_id.get(user_id)
        playing_handicap = tournament_personal_handicap(
            course,
            own_player,
            user.handicap.value if user and user.handicap else None,
            scratch=raw.scratch,
        )
        # En foursomes la pareja juega UNA bola, así que la tarjeta no es la
        # vuelta de ninguno de los dos por separado y no lleva puntos Stableford.
        # Los golpes del bando sí se enseñan, y son los mismos para los dos
        # compañeros. Es la misma regla que en partida rápida, donde vive en
        # `_to_quick_match_dto`: aquí se había quedado sin aplicar.
        is_foursomes = raw.round_.match_format == MatchFormat.FOURSOMES
        total_strokes, holes_played, points = self._scorecard_totals(
            raw, hole_card, playing_handicap, side_ball=is_foursomes
        )

        return RecentMatchDTO(
            id=str(match.id.value),
            date=raw.round_.round_date,
            match_format=raw.round_.match_format.value,
            # Un partido de torneo se juega siempre por hoyos: el eje MEDAL /
            # STABLEFORD es de las partidas rápidas y aquí no aplica
            scoring_format=None,
            golf_course_id=str(raw.round_.golf_course_id.value),
            golf_course_name=course.name if course else None,
            # Un partido de torneo no tiene nombre propio: tiene el de su
            # competición, que va en `tournament_name`
            match_name=None,
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
        return quick_match_strokes(raw.match, course, users_by_id, self._stroke_allocation_service)

    def _quick_match_play_outcome(
        self,
        raw: _QuickMatchRaw,
        strokes: dict[ParticipantId, ParticipantStrokes],
    ) -> tuple[str | None, str | None]:
        """
        Cómo quedó una partida rápida por equipos, desde el lado del jugador.

        Lo calcula `match_play_result`, la misma pieza que usan las partidas
        jugadas con un amigo (BE-3), con los golpes repartidos como en el
        detalle: si aquí se compararan los brutos, el historial contaría una
        película distinta de la que muestra la partida abierta.
        """
        rosters = raw.match.team_rosters()
        if rosters is None:
            return None, None
        team_a_ids, _ = rosters

        winner, score = match_play_result(
            raw.match,
            raw.scores_by_participant,
            strokes,
            self._scoring_service,
        )
        own_team = "A" if raw.participant.participant_id in team_a_ids else "B"
        return self._result_for_team(winner, own_team), score

    def _foursomes_side_strokes(
        self,
        raw: _QuickMatchRaw,
        course: GolfCourse | None,
        strokes: dict[ParticipantId, ParticipantStrokes],
    ) -> tuple[int, int] | None:
        """
        Golpes brutos y hoyos del BANDO en foursomes: una bola por hoyo.

        Normalmente hay una sola: el frontend guarda la bola a nombre del primer
        jugador del bando, la anote quien la anote. Si llegan dos se toma la
        MENOR, que es la que usa `MatchPlayScoring._best_ball` para adjudicar el
        hoyo: contar aquí una y adjudicar con la otra dejaría la partida con
        unos golpes que no explican su resultado. Lo que nunca se hace es
        sumarlas, porque comparten bola y eso doblaría la vuelta.

        Un hoyo RECOGIDO cuenta: está jugado, y lo decide el resultado del
        partido igual que cualquier otro. Vale su doble bogey NETO, `par + 2 +
        golpes recibidos` (Agustin, 23 oct 2026), con los golpes del bando en el
        partido (`strokes`): los dos comparten bola y reparto. Dejarlo fuera
        daba un total de menos hoyos de los que el partido dice que se jugaron.

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

            # El menor de los números, que es lo que hace `MatchPlayScoring._best_ball`
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
            del_bando = strokes.get(side_in_order[0])
            recibe = del_bando.strokes_on_hole(hole_number) if del_bando else 0
            total_strokes += self._calculator.net_double_bogey(par, recibe)
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
            for hole in course.hole_card_for(raw.participant.tee_color, raw.participant.tee_gender)
        ]
        # El hándicap de juego de su vuelta propia, con su barra como en la
        # partida: con el índice tal cual el panel daba 28 puntos a una vuelta
        # de 32 (BE #513). En una partida scratch sale 0, sin golpes
        playing_handicap = own_playing_handicap(
            raw.match,
            raw.participant,
            raw.participant.effective_handicap(profile_handicap),
            course,
        )
        # Sin barra ni allowance: ya van dentro del hándicap de juego, y el
        # calculador sin `tee_rating` reparte la cifra que recibe tal cual
        return self._calculator.compute_participant_totals(
            handicap=playing_handicap,
            holes=holes,
            scores_by_hole=scores_by_hole,
        )

    def _scorecard_totals(
        self,
        raw: _CompetitionMatchRaw,
        hole_card: list,
        playing_handicap: int | None,
        side_ball: bool = False,
    ) -> tuple:
        """
        Golpes, hoyos y puntos Stableford de una tarjeta de torneo.

        Los puntos con los golpes de su vuelta propia sobre el índice de su
        barra, no con los guardados en el hoyo, que son los del partido (BE
        #517). Se usa `own_score` y
        no `net_score` porque este último solo existe cuando el marcador validó
        el hoyo, y una tarjeta legítima sin validar cerrar se quedaría sin
        cifras que enseñar.
        """
        if not hole_card:
            return None, None, None

        pars = {hole.number: hole.par for hole in hole_card}
        stroke_index = {hole.number: hole.stroke_index for hole in hole_card}
        basis = None if playing_handicap is None else Decimal(playing_handicap)
        # Lo que el jugador apuntó, raya incluida: la raya es `own_score` None
        # con el envío hecho, y vale su doble bogey neto, `par + 2 + golpes
        # recibidos` (Agustin, 23 oct 2026), sin puntos. Con la bola del bando
        # (`side_ball`, foursomes) los golpes son los del bando en el partido,
        # los guardados en el hoyo: con los de cada uno, la misma bola daba dos
        # totales distintos
        scored = [
            hole_score
            for hole_score in raw.hole_scores
            if hole_score.own_submitted and hole_score.hole_number in pars
        ]
        if not scored:
            return None, None, None

        total_strokes = points = 0
        for hole_score in scored:
            par = pars[hole_score.hole_number]
            received = (
                hole_score.strokes_received
                if side_ball
                else self._calculator.allocate_strokes(basis, stroke_index[hole_score.hole_number])
            )
            if hole_score.own_score is None:
                total_strokes += self._calculator.net_double_bogey(par, received)
                continue
            total_strokes += hole_score.own_score
            points += self._calculator.hole_points(hole_score.own_score, par, received)
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
        """El nombre con el que se pinta a alguien: su alias si tiene (BE #239)."""
        user = users_by_id.get(user_id)
        return user.display_name if user else "Unknown"

    @classmethod
    def _participant_name(
        cls, participant: QuickMatchParticipant, users_by_id: dict[UserId, User]
    ) -> str:
        """Un invitado trae su nombre dentro de la partida; un registrado, en su perfil."""
        if participant.is_guest:
            return f"{participant.first_name} {participant.last_name}"
        return cls._user_name(participant.user_id, users_by_id)
