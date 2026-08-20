"""
Cuando un hoyo de una partida rapida cuenta para el resultado.

La regla vivia escrita a mano en cada pantalla que calcula el resultado —el
detalle de la partida y el historial— y solo se arreglo en una: el historial
seguia exigiendo los cuatro scores y dejaba **todas** las partidas de foursomes
sin resultado mientras el detalle ya las puntuaba. Vive aqui una sola vez.
"""

from src.modules.competition.domain.value_objects.match_format import MatchFormat

from ..value_objects.participant_id import ParticipantId


def hole_is_complete(
    scored_ids: set[ParticipantId] | dict[ParticipantId, int],
    team_a_ids: set[ParticipantId],
    team_b_ids: set[ParticipantId],
    match_format: MatchFormat | None,
) -> bool:
    """
    Un hoyo cuenta para el resultado cuando cada bando ha entregado su bola.

    FOURSOMES se juega a golpes alternos con UNA bola por bando, y la anota
    cualquiera de los dos companeros. Exigir los cuatro scores —que es lo
    correcto en FOURBALL, donde cada bando juega dos bolas y la mejor puede
    cambiar con la que falte— dejaba sin puntuar cualquier tarjeta llevada como
    se juega: el partido entero se quedaba sin un solo hoyo valido.

    Ojo con quien decide luego el hoyo: `ScoringService._best_ball` no mira el
    formato y devuelve el MENOR de los scores que reciba. En foursomes hay uno
    solo porque la bola del bando se guarda a nombre de un unico participante
    —el primero del bando, lo anote quien lo anote—, no porque el motor sepa que
    el bando juega una bola. Y dos filas del mismo bando con golpes distintos ya
    no es hipotetico: `ScoringCoverageService` da a los dos anotadores cobertura
    de los cuatro a proposito. Si llegan dos, gana la menor en silencio, no la
    ultima anotada.

    `match_format` admite None —una partida en juego libre no tiene formato— y
    entonces cae en la regla general de exigir a todos.

    Args:
        scored_ids: participantes con score en ese hoyo (basta la pertenencia)
        team_a_ids: participantes del bando A
        team_b_ids: participantes del bando B
        match_format: formato de la partida, o None en juego libre
    """
    if match_format == MatchFormat.FOURSOMES:
        return any(pid in scored_ids for pid in team_a_ids) and any(
            pid in scored_ids for pid in team_b_ids
        )
    return all(pid in scored_ids for pid in team_a_ids | team_b_ids)
