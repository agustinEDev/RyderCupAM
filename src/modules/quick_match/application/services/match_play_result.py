"""
El resultado de una partida rapida por hoyos, ya terminada.

Lo comparten el historial del jugador y las partidas jugadas con un amigo
(BE-3): las dos tienen que contar la misma pelicula que la partida abierta, y
escrito dos veces se separarian en cuanto cambiara una de las reglas.
"""

from collections.abc import Mapping
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


def match_play_result(
    match: QuickMatch,
    scores_by_participant: Mapping[ParticipantId, Mapping[int, int | None]],
    strokes_by_participant: Mapping[ParticipantId, ParticipantStrokes],
    scoring_service: MatchPlayScoring,
) -> tuple[str | None, str | None]:
    """
    Quien gano («A», «B» o «HALVED») y con que marcador, o `(None, None)`.

    El resultado no esta guardado en ningun sitio: se recalcula hoyo a hoyo con
    el mismo motor que usa el detalle de la partida. Solo cuentan los hoyos
    donde anotaron los dos bandos, porque un hoyo a medias no se puede
    adjudicar, y con la misma regla que el detalle —`hole_is_complete`— y no con
    una copia: escrita a mano, exigia los cuatro scores y dejaba sin resultado
    todas las partidas de foursomes mientras la partida abierta ya las puntuaba.
    """
    rosters = match.team_rosters()
    if rosters is None:
        return None, None
    team_a_ids, team_b_ids = rosters

    hole_results = []
    for hole_number in range(1, TOTAL_HOLES + 1):
        scores = {
            participant_id: holes[hole_number]
            for participant_id, holes in scores_by_participant.items()
            if hole_number in holes
        }
        if not hole_is_complete(scores, team_a_ids, team_b_ids, match.match_format):
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
            scoring_service.calculate_hole_winner(
                [net(pid) for pid in team_a_ids if pid in scores],
                [net(pid) for pid in team_b_ids if pid in scores],
                match.match_format,
            )
        )

    if not hole_results:
        return None, None

    standing = scoring_service.calculate_match_standing(hole_results)

    if scoring_service.is_match_decided(standing):
        # Se cerro antes del 18: el resultado va en "3&2", ventaja y hoyos
        # que quedaban
        outcome = scoring_service.format_decided_result(hole_results)
        return outcome["winner"], outcome["score"]

    if standing["leading_team"] is None:
        return HALVED_WINNER, "AS"

    # Terminado sin decidirse antes de tiempo: la ventaja tal cual ("2UP").
    # No vale `format_decided_result` aqui: inventaria un "2&7" con los hoyos
    # que quedaban sin anotar, como si el partido se hubiera cerrado en ellos
    return standing["leading_team"], standing["status"]
