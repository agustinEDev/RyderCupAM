"""
El desempate por hándicap de todas las clasificaciones (tabla del 22 oct 2026, H).

Ante un empate a puntos (Stableford) o a golpes netos (Medal), queda delante
quien tenga MENOS hándicap índice, exacto (12.4, no su hándicap de juego). Solo
comparten puesto quienes tienen exactamente el mismo. Quien no tiene hándicap
(solo pasa en la partida rápida: en un torneo no se entra sin él) cuenta como
0, igual que en el reparto de golpes de la partida (Agustín, 22 oct 2026): un
plus queda delante, un 0.0 comparte puesto con él.

Vive en `shared` porque la aplican la clasificación oficial de los torneos
(`competition`) y los puestos de la partida rápida y del cara a cara
(`social`): una sola regla, no dos copias.
"""

from decimal import Decimal

# Sin hándicap, el de un scratch
MISSING_HANDICAP = Decimal(0)


def handicap_tiebreak_key(handicap: Decimal | float | int | None) -> Decimal:
    """
    La clave que desempata, menor es mejor.

    Pasa por el texto del número para que 12.4 (float) y Decimal("12.40") sean
    el mismo hándicap: un float binario no lo es de un Decimal.
    """
    if handicap is None:
        return MISSING_HANDICAP
    return Decimal(str(handicap))
