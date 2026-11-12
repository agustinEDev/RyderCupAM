"""
De un fallo al generar los partidos al motivo que se apunta en la sesión (BE #360, #361).

Los errores con los que generar dice por qué no pudo, y su traducción a `MatchGenerationBlock`.
Lo usan el caso de uso que genera los partidos (el reintento a mano) y el EnvelopeDesk (la
apertura de los sobres): una sola traducción. Vivía en el caso de uso; aquí el EnvelopeDesk no
tiene que importar un caso de uso (ciclo B10, fase 5).
"""

from datetime import datetime

from src.modules.competition.application.exceptions import InsufficientPlayersError
from src.modules.competition.application.services.match_players_builder import (
    TeeColorNotFoundError,
)
from src.modules.competition.domain.value_objects.match_generation_block import (
    NO_GOLF_COURSE,
    NO_TEAMS,
    NOT_ENOUGH_PLAYERS,
    PLAYERS_WITHOUT_TEE,
    BlockedPlayer,
    MatchGenerationBlock,
)


class NoTeamAssignmentError(Exception):
    """No hay asignación de equipos."""

    pass


class PlayersWithoutTeeError(TeeColorNotFoundError):
    """Hay jugadores sin barras en el campo, y aquí van TODOS (BE #360, #361).

    Hereda del error de siempre para no cambiarle nada a quien ya lo captura.
    Lo que lee el organizador es la lista, en claves: la pantalla la pone en su
    idioma (decidido el 24 sep: claves siempre). El mensaje es para los logs.
    """

    def __init__(self, players: list[BlockedPlayer]):
        self.players = players
        super().__init__(
            "No se pueden generar los partidos: falta saber desde qué barras juegan "
            + _nombres(players)
        )


class PlayersNotEnrolledError(InsufficientPlayersError):
    """Hay emparejados sin la inscripción aprobada, y aquí van TODOS (BE #360).

    Hereda del error de siempre para no cambiarle nada a quien ya lo captura.
    """

    def __init__(self, players: list[BlockedPlayer]):
        self.players = players
        super().__init__(
            "No se pueden generar los partidos: no tienen la inscripción aprobada "
            + _nombres(players)
        )


def _nombres(players: list[BlockedPlayer]) -> str:
    """Para el mensaje, que acaba en los logs y en un cliente que aún no lee claves."""
    return ", ".join(p.name or "un jugador" for p in players)


class NoGolfCourseForHandicapError(ValueError):
    """Modo HANDICAP sin campo: no hay de dónde sacar las barras.

    Es un ValueError, como antes, para no cambiarle nada a quien lo captura.
    """

    pass


def bloqueo_por(error: Exception, at: datetime | None) -> MatchGenerationBlock | None:
    """El motivo que se apunta en la sesión por este fallo al generar (BE #360, #361).

    None si no es uno de los que se saben contar: lo inesperado no se disfraza
    de motivo. La apertura de los sobres, que nadie está mirando, lo apunta como
    UNEXPECTED; el reintento a mano lo deja subir como error.
    """
    if isinstance(error, PlayersWithoutTeeError):
        return MatchGenerationBlock(reason=PLAYERS_WITHOUT_TEE, players=tuple(error.players), at=at)
    # Antes que su clase madre: con él va quién
    if isinstance(error, PlayersNotEnrolledError):
        return MatchGenerationBlock(reason=NOT_ENOUGH_PLAYERS, players=tuple(error.players), at=at)
    if isinstance(error, InsufficientPlayersError):
        return MatchGenerationBlock(reason=NOT_ENOUGH_PLAYERS, at=at)
    if isinstance(error, NoTeamAssignmentError):
        return MatchGenerationBlock(reason=NO_TEAMS, at=at)
    if isinstance(error, NoGolfCourseForHandicapError):
        return MatchGenerationBlock(reason=NO_GOLF_COURSE, at=at)
    return None
