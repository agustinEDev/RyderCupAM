"""
TarjetaDeStrokePlay - Los totales de un jugador con sus hoyos validados (#251, PR 5).

Solo cuentan los hoyos validados (jugador y marcador coinciden). Los golpes que
recibe y el par de cada hoyo salen de la foto de su partida (P12), no del campo
de hoy.

- Stableford: puntos netos (con sus golpes) y brutos (sin golpes, el scratch, P13).
- Medal: golpes brutos (el scratch) y netos, y su resultado respecto al par de
  los hoyos jugados, para comparar a quien va por el 5 con quien va por el 12.
- La raya (solo en Stableford) vale 0 puntos y cuenta como hoyo jugado.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from src.shared.domain.services.stroke_play_scoring import StrokePlayScoring

from ..value_objects.jugador_de_partida import HOYOS, JugadorDePartida


@dataclass(frozen=True)
class Tarjeta:
    """Los totales de lo validado."""

    puntos: int
    puntos_brutos: int
    golpes_brutos: int
    golpes_netos: int
    par_jugado: int
    tras: int
    con_raya: bool

    @property
    def completa(self) -> bool:
        return self.tras == HOYOS

    @property
    def al_par_neto(self) -> int:
        return self.golpes_netos - self.par_jugado

    @property
    def al_par_bruto(self) -> int:
        return self.golpes_brutos - self.par_jugado


class TarjetaDeStrokePlay:
    """Calcula la tarjeta de un jugador."""

    @staticmethod
    def de(foto: JugadorDePartida, validados: Mapping[int, int | None]) -> Tarjeta:
        """
        Args:
            foto: Su foto en la partida: golpes recibidos y par de cada hoyo
            validados: hoyo -> golpes validados (None, una raya)
        """
        puntos = puntos_brutos = brutos = netos = par_jugado = 0
        for hoyo, golpes in validados.items():
            recibidos = foto.golpes_por_hoyo[hoyo - 1]
            par = foto.par_por_hoyo[hoyo - 1]
            puntos += StrokePlayScoring.hole_points(golpes, par, recibidos)
            puntos_brutos += StrokePlayScoring.hole_points(golpes, par, 0)
            if golpes is not None:
                brutos += golpes
                netos += golpes - recibidos
                par_jugado += par
        return Tarjeta(
            puntos=puntos,
            puntos_brutos=puntos_brutos,
            golpes_brutos=brutos,
            golpes_netos=netos,
            par_jugado=par_jugado,
            tras=len(validados),
            con_raya=any(golpes is None for golpes in validados.values()),
        )
