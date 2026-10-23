"""Puestos de una clasificacion con empates (BE-2) y su desempate (H)."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from src.shared.domain.services.handicap_tiebreak import handicap_tiebreak_key


@dataclass(frozen=True)
class Puesto:
    """El puesto de uno y si lo comparte con alguien."""

    position: int
    tied: bool


def rank(
    values: Sequence[int],
    handicaps: Sequence[Decimal | float | None],
    higher_is_better: bool,
) -> list[Puesto]:
    """
    El puesto de cada valor, en el orden en que llegan; `handicaps[i]` es el
    índice con el que jugó el de `values[i]`.

    **A igual valor, delante el de menos hándicap** (tabla del 22 oct 2026, H),
    como en la general de un torneo (`Clasificacion`). Solo comparten puesto
    quienes tienen el mismo valor y el mismo hándicap exacto, y entonces el
    siguiente salta (1, 1, 3). Sin hándicap cuenta como 0.
    """
    signo = -1 if higher_is_better else 1
    claves = [
        (signo * valor, handicap_tiebreak_key(handicap))
        for valor, handicap in zip(values, handicaps, strict=True)
    ]
    return [
        Puesto(
            position=sum(1 for otra in claves if otra < clave) + 1,
            tied=claves.count(clave) > 1,
        )
        for clave in claves
    ]
