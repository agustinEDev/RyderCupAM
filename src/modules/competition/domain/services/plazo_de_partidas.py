"""
PlazoDePartidas - Cuándo se pueden generar y tocar las partidas de una franja (#251).

Decidido con Agustín el 8-9 oct 2026 (D11): del cierre de inscripciones hasta la
primera salida de la franja, y mientras no haya salido ninguna. Mover, reordenar
y cambiar marcadores tienen el mismo plazo que generar.

Aquí solo está la regla; la hora de la primera salida, con su zona horaria, la
calcula quien llama.
"""

from collections.abc import Sequence
from datetime import datetime

from ..entities.partida import Partida, PartidaEmpezadaError
from ..value_objects.competition_status import CompetitionStatus

ESTADOS_CON_PARTIDAS = frozenset({CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS})


class PlazoCerradoError(ValueError):
    """Fuera del plazo para generar o tocar las partidas."""


class PlazoDePartidas:
    """El plazo de las partidas de una franja."""

    @staticmethod
    def comprobar(
        estado: CompetitionStatus,
        primera_salida: datetime,
        ahora: datetime,
        partidas: Sequence[Partida],
    ) -> None:
        """
        Args:
            estado: El de la competición
            primera_salida: La hora de la primera salida de la franja, con zona
            ahora: El momento de la petición, con zona
            partidas: Las que ya tiene la franja

        Raises:
            PlazoCerradoError: Si la competición no está cerrada o iniciada, o ya
                es la hora de la primera salida
            PartidaEmpezadaError: Si alguna partida ya ha salido
        """
        if estado not in ESTADOS_CON_PARTIDAS:
            raise PlazoCerradoError(
                "Las partidas se hacen con las inscripciones cerradas, antes de la primera salida."
            )
        if ahora >= primera_salida:
            raise PlazoCerradoError("La franja ya ha empezado: las partidas no se pueden cambiar.")
        if any(p.empezada for p in partidas):
            raise PartidaEmpezadaError("Ya ha salido alguna partida de la franja.")
