"""
Si la competición de un partido de match play se está jugando (SB-03, 16 nov 2026).

Anotar, conceder, entregar la tarjeta o retirar a un jugador cambian el resultado
del partido, y eso solo se hace con la competición en juego. Antes se miraba solo
el estado del partido: con la competición ya terminada o cancelada, un partido que
se quedó abierto se seguía anotando. La regla es la del dominio
(`CompetitionStatus.admite_anotar`), la misma que en el stroke play.
"""

from src.modules.competition.application.exceptions import MatchNotScoringError
from src.modules.competition.domain.entities.competition import Competition


def exigir_competicion_en_juego(competition: Competition | None) -> Competition:
    """
    La competición del partido, si se está jugando.

    Raises:
        MatchNotScoringError: Si no existe o no está cerrada ni en juego (409, como
            el de un partido que ya no se anota)
    """
    if competition is None or not competition.status.admite_anotar():
        estado = competition.status.value if competition is not None else "desconocido"
        raise MatchNotScoringError(f"La competicion no esta en juego. Estado: {estado}")
    return competition
