"""
La vuelta propia: «¿cómo jugué yo?» (decisión del 18 ago 2026).

Se mide con el hándicap de juego ENTERO del jugador contra el campo, con la
pendiente y el rating de su barra. El allowance de cada formato (95 % libre,
90 % fourball...) y el reparto por diferencia del match play equilibran un
partido, no miden una vuelta: con ellos la misma vuelta valía distinto según el
formato o el rival. Lo usan la partida rápida, el historial del panel y las
estadísticas, para que las tres midan igual (BE #513, #517).
"""

from decimal import Decimal

from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
    TeeRating,
    round_half_up,
)

PERSONAL_ROUND_ALLOWANCE = 100


def personal_playing_handicap(
    handicap_index: float | Decimal | None,
    tee_rating: TeeRating | None,
    *,
    scratch: bool = False,
) -> int | None:
    """
    Hándicap de juego de la vuelta propia.

    None sin índice conocido; 0 si se jugó a scratch; el índice redondeado si la
    barra no se puede valorar (como hace la partida con quien no tiene barra).
    """
    if handicap_index is None:
        return None
    if scratch:
        return 0
    index = Decimal(str(handicap_index))
    if tee_rating is None:
        return round_half_up(index)
    return PlayingHandicapCalculator().calculate(index, tee_rating, PERSONAL_ROUND_ALLOWANCE)
