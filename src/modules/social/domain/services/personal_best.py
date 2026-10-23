"""
Domain Service: la marca con la que se mide un record. Puro, sin IO.

Un record solo se mide contra las vueltas de dias ANTERIORES (decision de
Agustin, 23 oct 2026): un record del 12 oct que «mejora su 35.6» no puede
estar comparandose con un 35.6 del 15 oct, que se cerro antes por casualidad.
Las del mismo dia no cuentan como anteriores, porque las estadisticas solo
guardan el dia de cada vuelta, no la hora.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.modules.social.domain.services.achievement_detector import RoundContext
from src.shared.domain.services.score_differential_calculator import (
    ScoreDifferentialCalculator,
)


@dataclass(frozen=True)
class DatedDifferential:
    """
    El diferencial de una vuelta computable, con su dia y de donde sale: la
    partida rapida, el partido de la Ryder o el grupo de stroke play
    (`source_id`), y su torneo si lo tiene (`competition_id`).
    """

    played_on: date
    differential: Decimal
    source_id: str | None = None
    competition_id: str | None = None


def record_context(
    rondas: Sequence[DatedDifferential],
    es_suya: Callable[[DatedDifferential], bool],
) -> RoundContext:
    """
    Con que se juzga el record de lo que `es_suya` (una partida rapida, o
    todas las vueltas de un torneo):

    - su diferencial, el mejor de las suyas (un torneo se mide una vez);
    - la marca anterior, la mejor de las vueltas de dias anteriores al primero
      de las suyas, dentro de la misma ventana del WHS que las estadisticas
      (las 20 mas recientes de esas).

    Sin vueltas suyas no hay nada que juzgar. Sin anteriores no hay marca, y
    el detector no publica record: la primera es el punto de partida.
    """
    suyas = [r for r in rondas if es_suya(r)]
    if not suyas:
        return RoundContext()
    primer_dia = min(r.played_on for r in suyas)
    anteriores = sorted(
        (r for r in rondas if r.played_on < primer_dia),
        key=lambda r: r.played_on,
        reverse=True,
    )
    return RoundContext(
        previous_best_differential=ScoreDifferentialCalculator.best_differential(
            [r.differential for r in anteriores]
        ),
        differential=min(r.differential for r in suyas),
    )
