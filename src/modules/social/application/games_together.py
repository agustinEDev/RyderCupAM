"""
El cara a cara y la lista de partidas juntos, a partir de las partidas leidas.

Vive aparte porque lo comparten el perfil (cara a cara y primera pagina) y el
«ver mas» de las partidas juntos: los dos tienen que ordenar y paginar igual.
"""

from datetime import date, datetime, time
from uuid import UUID

from src.modules.social.application.dto.head_to_head_dto import (
    GamesTogetherPageDTO,
    GameTogetherDTO,
    HeadToHeadDTO,
    HeadToHeadRecordDTO,
)
from src.modules.social.application.feed_cursor import parse_instant
from src.modules.social.application.ports.shared_games_interface import (
    SharedGame,
    SharedGameKind,
)
from src.modules.social.domain.services.head_to_head import Record, tally
from src.shared.domain.services.instante_utc import en_utc

# La fecha en ISO no contiene '|', asi que parte el cursor sin ambiguedad
CURSOR_SEPARATOR = "|"

# Dia, instante e id
_PARTES_DEL_CURSOR = 3

# La partida rapida que no cuenta por los hoyos anotados (tabla del 22 oct, A)
UNFINISHED_RESULT = "UNFINISHED"

# De 5 en 5, con «ver mas» (tabla aprobada del 22 oct)
GAMES_PAGE_SIZE = 5


def head_to_head_of(games: list[SharedGame]) -> HeadToHeadDTO | None:
    """El cara a cara, o None si no hay ninguna partida que contar."""
    cara_a_cara = tally((game.relation, game.outcome) for game in games)
    if cara_a_cara is None:
        return None
    return HeadToHeadDTO(
        against=_record(cara_a_cara.against), alongside=_record(cara_a_cara.alongside)
    )


def page_of(
    games: list[SharedGame], cursor: str | None, limit: int = GAMES_PAGE_SIZE
) -> GamesTogetherPageDTO:
    """
    Una pagina, de la mas reciente a la mas antigua, a partir del cursor.

    Se ordena por dia, dentro del dia por el instante en que se jugo y, a la
    misma hora, por id: el id solo desempata, asi que dos partidas del mismo
    dia salen por su hora y ninguna se pierde ni se repite entre paginas. Un
    cursor corrupto da la primera pagina, como el del feed.
    """
    ordenadas = sorted(games, key=_clave, reverse=True)
    desde = _parse_cursor(cursor)
    if desde is not None:
        ordenadas = [game for game in ordenadas if _clave(game) < desde]

    pagina = ordenadas[:limit]
    hay_mas = len(ordenadas) > limit
    return GamesTogetherPageDTO(
        games=[_to_dto(game) for game in pagina],
        next_cursor=_build_cursor(pagina[-1]) if hay_mas else None,
    )


def _clave(game: SharedGame) -> tuple[date, datetime, str]:
    """
    Dia, instante e id. El dia va primero aunque el instante ya lo lleve: el
    instante esta en UTC y el dia es el del campo, y la lista no puede pintar
    un dia antes que el siguiente. Sin instante conocido, el principio del dia.
    """
    instante = game.played_at or datetime.combine(game.played_on, time.min)
    return game.played_on, instante, game.game_id


def _build_cursor(game: SharedGame) -> str:
    dia, instante, game_id = _clave(game)
    return CURSOR_SEPARATOR.join((dia.isoformat(), instante.isoformat(), game_id))


def _parse_cursor(cursor: str | None) -> tuple[date, datetime, str] | None:
    """
    El cursor de vuelta, o None si no vale. El instante se lee como el del
    feed: una fecha que se sale del calendario al pasarla a UTC no tumba la
    peticion, cuenta como corrupta.
    """
    if not cursor:
        return None
    partes = cursor.split(CURSOR_SEPARATOR)
    if len(partes) != _PARTES_DEL_CURSOR:
        return None
    dia_raw, instante_raw, game_id = partes
    instante = parse_instant(instante_raw)
    if instante is None:
        return None
    try:
        dia = date.fromisoformat(dia_raw)
        UUID(game_id)
    except ValueError:
        return None
    return dia, instante, game_id


def _record(record: Record | None) -> HeadToHeadRecordDTO | None:
    if record is None:
        return None
    return HeadToHeadRecordDTO(won=record.won, halved=record.halved, lost=record.lost)


def _resultado(game: SharedGame) -> str | None:
    """WON, HALVED o LOST; UNFINISHED si no cuenta por los hoyos; None si no se juzga."""
    if game.unfinished:
        return UNFINISHED_RESULT
    return game.outcome.value if game.outcome else None


def _to_dto(game: SharedGame) -> GameTogetherDTO:
    rapida = game.kind == SharedGameKind.QUICK_MATCH
    # El torneo entero: su id es el del torneo, no hay partido ni grupo (J)
    torneo = game.kind == SharedGameKind.TOURNAMENT_STROKE_PLAY
    puestos = game.standing
    return GameTogetherDTO(
        kind=game.kind.value,
        id=game.game_id,
        played_on=game.played_on,
        played_at=en_utc(game.played_at) if rapida else None,
        golf_course_id=game.golf_course_id,
        golf_course_name=game.golf_course_name,
        format=game.format,
        relation=game.relation.value,
        result=_resultado(game),
        quick_match_id=game.game_id if rapida else None,
        competition_id=game.competition_id,
        competition_name=game.competition_name,
        match_id=None if rapida or torneo else game.game_id,
        my_position=puestos.my_position if puestos else None,
        my_tied=puestos.my_tied if puestos else None,
        their_position=puestos.their_position if puestos else None,
        their_tied=puestos.their_tied if puestos else None,
        total_players=puestos.total_players if puestos else None,
    )
