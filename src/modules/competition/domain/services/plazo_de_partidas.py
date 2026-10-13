"""
PlazoDePartidas - Cuándo se pueden generar y tocar las partidas de una franja (#251).

Decidido con Agustín el 8-9 oct 2026 (D11): del cierre de inscripciones hasta la
primera salida de la franja, y mientras no haya salido ninguna, para generarlas o
borrarlas. Mover, reordenar y cambiar marcadores valen también con la franja
empezada, en las partidas que aún no han salido (#544, 13 oct 2026): las que ya
salieron (les llegó la hora o tienen golpes) no se tocan.

Aquí solo está la regla; la hora de la primera salida, con su zona horaria, la
calcula quien llama.
"""

from collections.abc import Collection, Sequence
from datetime import date, datetime

from ..entities.partida import Partida, PartidaEmpezadaError
from ..value_objects.competition_status import CompetitionStatus
from ..value_objects.hoja_de_salidas import HojaDeSalidas
from ..value_objects.partida_id import PartidaId

ESTADOS_CON_PARTIDAS = frozenset({CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS})


class PlazoCerradoError(ValueError):
    """Fuera del plazo para generar o tocar las partidas."""


class PartidaYaSalidaError(ValueError):
    """Esa partida ya ha salido (su hora llegó o tiene golpes): no se toca (#544)."""


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

    @staticmethod
    def salidas(
        partidas: Sequence[Partida],
        hoja: HojaDeSalidas,
        primera_salida: datetime,
        ahora: datetime,
    ) -> set[PartidaId]:
        """
        Las que ya han salido: les llegó su hora o ya tienen golpes (#544).

        La hora de cada una es la de la primera más lo que va de la primera a la
        suya en la hoja: el mismo día, sin cambio de hora en medio (la franja que
        cae en el hueco del cambio de hora no se puede crear).
        """
        dia = date(2000, 1, 1)
        inicio = datetime.combine(dia, hoja.hora_de(1))
        return {
            p.id
            for p in partidas
            if p.empezada
            or primera_salida + (datetime.combine(dia, hoja.hora_de(p.numero)) - inicio) <= ahora
        }

    @staticmethod
    def comprobar_que_se_pueden_tocar(
        estado: CompetitionStatus,
        tocadas: Sequence[Partida],
        salidas: Collection[PartidaId],
    ) -> None:
        """
        Mover, reordenar o cambiar marcadores: solo partidas que aún no han salido,
        también con la franja empezada (#544).

        Raises:
            PlazoCerradoError: Si la competición no está cerrada o iniciada
            PartidaYaSalidaError: Si alguna de las tocadas ya ha salido
        """
        if estado not in ESTADOS_CON_PARTIDAS:
            raise PlazoCerradoError(
                "Las partidas se tocan con las inscripciones cerradas o la competición en juego."
            )
        if any(p.id in salidas for p in tocadas):
            raise PartidaYaSalidaError("Esa partida ya ha salido: no se puede cambiar.")
