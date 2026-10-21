"""Puestos de una clasificacion con empates (BE-2)."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Puesto:
    """El puesto de uno y si lo comparte con alguien."""

    position: int
    tied: bool


def rank(values: Sequence[int], higher_is_better: bool) -> list[Puesto]:
    """
    El puesto de cada valor, en el orden en que llegan.

    **Los empatados comparten puesto y el siguiente salta** (1, 1, 3), como en
    la general de un torneo (`Clasificacion`, P5): sin desempate automatico.
    """
    if higher_is_better:
        mejores_que = [sum(1 for otro in values if otro > valor) for valor in values]
    else:
        mejores_que = [sum(1 for otro in values if otro < valor) for valor in values]
    return [
        Puesto(position=delante + 1, tied=values.count(valor) > 1)
        for delante, valor in zip(mejores_que, values, strict=True)
    ]
