"""
La vuelta propia: «¿cómo jugué yo?» (decisión del 18 ago 2026).

Se mide con el hándicap de juego ENTERO del jugador contra el campo, con la
pendiente y el rating de su barra. El allowance de cada formato (95 % libre,
90 % fourball...) y el reparto por diferencia del match play equilibran un
partido, no miden una vuelta: con ellos la misma vuelta valía distinto según el
formato o el rival. Lo usan las estadísticas, para medir igual partida rápida y
torneo (BE #513, #517). El historial ya no: «Tu vuelta» es la real de la
partida, con el allowance de su modalidad (Agustín, 24 oct 2026).
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
    allowance: int = PERSONAL_ROUND_ALLOWANCE,
) -> int | None:
    """
    Hándicap de juego de la vuelta propia.

    None sin índice conocido; 0 si se jugó a scratch; el índice con el allowance,
    redondeado, si la barra no se puede valorar (como hace la partida con quien
    no tiene barra). Al 100 % por defecto, que es lo que miden las estadísticas;
    el historial pasa el de la modalidad (Agustín, 24 oct 2026).
    """
    if handicap_index is None:
        return None
    if scratch:
        return 0
    index = Decimal(str(handicap_index))
    if tee_rating is None:
        return round_half_up(index * allowance / 100)
    return PlayingHandicapCalculator().calculate(index, tee_rating, allowance)
