"""
Si la competición se está jugando: lo único en que se anota (SB-03, 16 nov 2026).

Una sola comprobación para el stroke play y el match play. La regla es la del dominio
(`CompetitionStatus.admite_anotar`: cerrada o en juego); cada caso de uso dice con qué
error se rechaza, porque cada API responde el suyo (`PartidaNoAnotableError` con su
`error_code` en el stroke play, el 409 `MatchNotScoringError` de siempre en el match
play).

En match play, anotar, conceder, entregar la tarjeta o retirar a un jugador cambian el
resultado del partido. Antes se miraba solo el estado del partido: con la competición
ya terminada o cancelada, un partido que se quedó abierto se seguía anotando.
"""

from collections.abc import Callable

from src.modules.competition.application.exceptions import MatchNotScoringError
from src.modules.competition.domain.entities.competition import Competition


def exigir_competicion_en_juego(
    competition: Competition | None,
    error: Callable[[Competition | None], Exception],
) -> Competition:
    """
    La competición, si se está jugando.

    Args:
        competition: La competición, o None si no existe
        error: Qué error lanzar si no se juega, a partir de la competición (o None)

    Raises:
        Lo que devuelva `error`: si no existe o no está cerrada ni en juego
    """
    if competition is None or not competition.status.admite_anotar():
        raise error(competition)
    return competition


def partido_no_anotable(competition: Competition | None) -> MatchNotScoringError:
    """El 409 del match play: el mismo que un partido que ya no se anota."""
    estado = competition.status.value if competition is not None else "desconocido"
    return MatchNotScoringError(f"La competicion no esta en juego. Estado: {estado}")
