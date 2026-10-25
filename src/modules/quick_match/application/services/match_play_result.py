"""
El resultado de una partida rapida por hoyos, ya terminada.

Lo comparten el historial del jugador, las partidas jugadas con un amigo (BE-3)
y Actividad: tienen que contar la misma pelicula que la partida abierta, y
escrito dos veces se separarian en cuanto cambiara una de las reglas.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.quick_match.application.services.course_context import course_context_for
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.services.hole_completion_service import hole_is_complete
from src.modules.quick_match.domain.services.stroke_allocation_service import (
    ParticipantStrokes,
    StrokeAllocationService,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.match_play_scoring import MatchPlayScoring

# `GolfCourse` valida exactamente 18 hoyos como invariante
TOTAL_HOLES = 18
HALVED_WINNER = "HALVED"


def quick_match_strokes(
    match: QuickMatch,
    course: GolfCourse | None,
    users_by_id: Mapping[UserId, User],
    service: StrokeAllocationService,
) -> dict[ParticipantId, ParticipantStrokes]:
    """
    Reparto de golpes de una partida rapida, como en su detalle.

    Sin el campo (borrado, o no cargado) se devuelve un reparto vacio: quien lo
    use decide si un resultado a bruto le vale o no.
    """
    if course is None:
        return {}

    context = course_context_for(course)
    handicaps: dict[ParticipantId, Decimal | None] = {}
    for participant in match.participants:
        # Lo decide el participante: el fijado al empezar (BE #514) o, en
        # partidas de antes, el manual, el personalizado o el del perfil
        user = users_by_id.get(participant.user_id) if participant.user_id else None
        value = participant.effective_handicap(
            user.handicap.value if user and user.handicap else None
        )
        handicaps[participant.participant_id] = None if value is None else Decimal(str(value))

    return service.allocate(
        participants=match.participants,
        handicaps=handicaps,
        tee_ratings=context.tee_ratings,
        holes_by_stroke_index=context.holes_by_stroke_index,
        holes_by_stroke_index_by_tee=context.holes_by_tee,
        match_format=match.match_format,
        allowance_percentage=match.get_effective_allowance(),
        play_mode=match.play_mode,
    )


@dataclass(frozen=True)
class MatchPlayReading:
    """
    Lo que dice un match play rapido terminado.

    `winner` es «A», «B» o «HALVED» (None sin ningun hoyo que adjudicar),
    `score` el tanteo («3&2», «2UP», «AS»), `holes_played` los hoyos que
    cuentan para el resultado y `decided_early` si se cerro antes de quedarse
    sin hoyos (un «3&2»).
    """

    winner: str | None
    score: str | None
    holes_played: int
    decided_early: bool


def match_play_reading(
    match: QuickMatch,
    scores_by_participant: Mapping[ParticipantId, Mapping[int, int | None]],
    strokes_by_participant: Mapping[ParticipantId, ParticipantStrokes],
    scoring_service: MatchPlayScoring,
) -> MatchPlayReading:
    """
    Quien gano, con que marcador, cuantos hoyos cuentan y si se decidio antes
    de tiempo.

    El resultado no esta guardado en ningun sitio: se recalcula hoyo a hoyo con
    el mismo motor que usa el detalle de la partida. Solo cuentan los hoyos
    donde anotaron los dos bandos, porque un hoyo a medias no se puede
    adjudicar, y con la misma regla que el detalle —`hole_is_complete`— y no con
    una copia: escrita a mano, exigia los cuatro scores y dejaba sin resultado
    todas las partidas de foursomes mientras la partida abierta ya las puntuaba.

    En fourball hacen falta las cuatro bolas, tambien en lo social (Agustin, 24
    oct 2026; deshace la bola de uno por bando del 22 oct).
    """
    regla = match.match_format
    sin_resultado = MatchPlayReading(None, None, 0, decided_early=False)
    rosters = match.team_rosters()
    if rosters is None:
        return sin_resultado
    team_a_ids, team_b_ids = rosters

    results_by_hole: dict[int, str] = {}
    for hole_number in range(1, TOTAL_HOLES + 1):
        scores = {
            participant_id: holes[hole_number]
            for participant_id, holes in scores_by_participant.items()
            if hole_number in holes
        }
        if not hole_is_complete(scores, team_a_ids, team_b_ids, regla):
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
        results_by_hole[hole_number] = scoring_service.calculate_hole_winner(
            [net(pid) for pid in team_a_ids if pid in scores],
            [net(pid) for pid in team_b_ids if pid in scores],
            match.match_format,
        )

    if not results_by_hole:
        return sin_resultado

    hole_results = list(results_by_hole.values())
    jugados = len(hole_results)
    standing = scoring_service.calculate_match_standing(hole_results)

    # Decidido en el orden de los hoyos, como en los torneos: con un hoyo sin
    # cerrar antes no lo esta (Agustin, 25 oct 2026). Si se cerro antes del 18,
    # el resultado va en "3&2", ventaja y hoyos que quedaban
    hasta_la_decision = scoring_service.holes_until_decided(results_by_hole)
    if hasta_la_decision is not None:
        outcome = scoring_service.format_decided_result(hasta_la_decision)
        return MatchPlayReading(
            outcome["winner"],
            outcome["score"],
            # Los que cuentan: hasta la decision, como la pantalla
            len(hasta_la_decision),
            # "3&2" antes del 18; "1UP" en el 18
            decided_early=len(hasta_la_decision) < TOTAL_HOLES,
        )

    if standing["leading_team"] is None:
        return MatchPlayReading(HALVED_WINNER, "AS", jugados, decided_early=False)

    # Terminado sin decidirse antes de tiempo: la ventaja tal cual ("2UP").
    # No vale `format_decided_result` aqui: inventaria un "2&7" con los hoyos
    # que quedaban sin anotar, como si el partido se hubiera cerrado en ellos
    return MatchPlayReading(
        standing["leading_team"], standing["status"], jugados, decided_early=False
    )
