"""
Reparto de golpes por hoyo, una sola pieza para competición y partida rápida
(BE #165).

Había tres copias que no coincidían: la de competición ignoraba el hándicap
plus y las otras dos lo cedían. La regla vive aquí una vez y las tres formas de
pedirla (un hoyo, el reparto entero, la lista que guarda la competición) se
construyen sobre ella.

Un Playing Handicap positivo se reparte del hoyo más difícil (stroke index 1)
al más fácil, dando la vuelta cuando pasa del número de hoyos. Uno negativo
(hándicap plus) se cede empezando por el más fácil y hacia atrás.
"""

from collections.abc import Sequence

HOLES_PER_ROUND = 18


def strokes_on_hole(
    playing_handicap: int, stroke_index: int, total_holes: int = HOLES_PER_ROUND
) -> int:
    """
    Golpes que recibe (positivo) o cede (negativo) un jugador en un hoyo.

    `stroke_index` va de 1 (el más difícil) a `total_holes` (el más fácil).
    """
    if playing_handicap == 0:
        return 0

    sign = 1 if playing_handicap > 0 else -1
    base, remainder = divmod(abs(playing_handicap), total_holes)
    # Al plus se le cuenta la dificultad al revés: su "primer" hoyo es el más fácil
    position = stroke_index if sign > 0 else total_holes + 1 - stroke_index
    extra = 1 if remainder >= position else 0
    return sign * (base + extra)


def allocate_by_hole(playing_handicap: int, holes_by_stroke_index: Sequence[int]) -> dict[int, int]:
    """
    Reparto entero por número de hoyo, con signo.

    Solo devuelve los hoyos con golpe, para no arrastrar 18 ceros.
    """
    total_holes = len(holes_by_stroke_index)
    allocation: dict[int, int] = {}
    for position, hole_number in enumerate(holes_by_stroke_index, start=1):
        count = strokes_on_hole(playing_handicap, position, total_holes)
        if count:
            allocation[hole_number] = count
    return allocation


def holes_receiving_strokes(
    playing_handicap: int, holes_by_stroke_index: Sequence[int]
) -> list[int]:
    """
    Hoyos donde se recibe golpe, en el formato que guarda la competición.

    Un hoyo aparece tantas veces como golpes recibe, vuelta a vuelta en orden de
    dificultad: con 20 golpes, los 18 hoyos y después los dos más difíciles.

    Solo sabe de golpes recibidos: un Playing Handicap negativo no recibe nada.
    """
    allocation = allocate_by_hole(playing_handicap, holes_by_stroke_index)
    passes = max(allocation.values(), default=0)
    return [
        hole
        for current_pass in range(passes)
        for hole in holes_by_stroke_index
        if allocation.get(hole, 0) > current_pass
    ]
