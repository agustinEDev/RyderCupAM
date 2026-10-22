"""
Domain Service: cuando cuenta una partida rapida en lo social (22 oct 2026).

Tabla aprobada por Agustin (bloque A). Solo partidas rapidas: los torneos no
cambian. Lo usan el cara a cara, «Partidas juntos» y el aviso de Actividad de
como acabo cada uno.

- **La referencia es el maximo de hoyos** que tiene alguien (un jugador, o un
  bando en match play).
- **Cuentan quienes tienen exactamente ese mismo conjunto de hoyos**, siempre
  que sean 9 o mas. Quien tiene menos no entra en la clasificacion ni en el
  cara a cara: sale «sin terminar».
- **Con menos de 9 de referencia no cuenta nadie.**
- **Si varios conjuntos distintos llegan al maximo** (la ida frente a la
  vuelta), no hay una referencia y no cuenta nadie: no se compara lo que no se
  jugo igual. Lo confirmo Agustin el 22 oct 2026.
- **Un match play decidido antes de tiempo («3&2») cuenta siempre.**

Puro, sin IO: recibe los hoyos ya leidos.
"""

from collections.abc import Collection, Hashable, Iterable, Mapping
from typing import TypeVar

# Media vuelta: lo minimo que se juega y se cuenta
MIN_COUNTED_HOLES = 9

K = TypeVar("K", bound=Hashable)


def counting_units(holes_by_unit: Mapping[K, Iterable[int]]) -> frozenset[K]:
    """Quienes cuentan: los que tienen exactamente los hoyos de la referencia."""
    conjuntos = {unidad: frozenset(hoyos) for unidad, hoyos in holes_by_unit.items()}
    if not conjuntos:
        return frozenset()
    maximo = max(len(hoyos) for hoyos in conjuntos.values())
    if maximo < MIN_COUNTED_HOLES:
        return frozenset()
    referencias = {hoyos for hoyos in conjuntos.values() if len(hoyos) == maximo}
    if len(referencias) != 1:
        return frozenset()
    (referencia,) = referencias
    return frozenset(unidad for unidad, hoyos in conjuntos.items() if hoyos == referencia)


def holes_by_side(
    scores_by_player: Mapping[K, Mapping[int, int | None]], side: Collection[K]
) -> frozenset[int]:
    """
    Los hoyos que entrego un bando: los que anoto al menos uno de sus jugadores.

    En fourball cuenta el mejor hoyo del bando, asi que basta la bola de uno
    (Agustin, 22 oct 2026); en foursomes el bando juega una sola bola; en
    individual, el bando es el jugador. La raya (score nulo) es un hoyo
    entregado: recogio la bola, pero el hoyo esta acabado.
    """
    return frozenset(hoyo for jugador in side for hoyo in scores_by_player.get(jugador, {}))


def match_play_counts(holes_a: Iterable[int], holes_b: Iterable[int], decided_early: bool) -> bool:
    """
    Si un match play cuenta: decidido antes de tiempo, o los dos bandos con los
    mismos hoyos y al menos 9.
    """
    if decided_early:
        return True
    return counting_units({"A": holes_a, "B": holes_b}) == {"A", "B"}
