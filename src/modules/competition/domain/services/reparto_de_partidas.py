"""
RepartoDePartidas - Cómo se reparten los jugadores de una franja en partidas (#251).

Decidido con Agustín el 8-9 oct 2026:

- Por **hándicap fijado**, en el orden que elija el organizador: los más altos
  primero o los más bajos primero.
- A igual hándicap, sale antes **quien cogió antes la plaza** (D6).
- Partidas del tamaño de la hoja de salidas; si sobrara uno solo, **la
  penúltima cede uno**: 13 de 4 son 4, 4, 3 y 2, nunca 4, 4, 4 y 1. Una partida
  de 1 solo queda por bajas (D4), nunca al generar.

Caben siempre: el cupo de la franja es salidas por tamaño de partida.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.modules.user.domain.value_objects.user_id import UserId

from ..value_objects.orden_de_salida import OrdenDeSalida
from .marcadores_en_cadena import MIN_PARA_MARCAR


class RepartoImposibleError(ValueError):
    """No se pueden repartir en partidas, y el mensaje dice por qué."""


@dataclass(frozen=True)
class ParaRepartir:
    """Lo que cuenta para repartir a un jugador: su hándicap fijado y cuándo cogió la plaza."""

    user_id: UserId
    handicap: Decimal
    plaza_cogida: datetime


class RepartoDePartidas:
    """El reparto de una franja en partidas."""

    @staticmethod
    def repartir(
        jugadores: Sequence[ParaRepartir], jugadores_por_partida: int, orden: OrdenDeSalida
    ) -> list[list[UserId]]:
        """
        Returns:
            Las partidas en orden de salida, cada una con sus jugadores en orden

        Raises:
            RepartoImposibleError: Con nadie (se borrarían las que hubiera) o con uno
                solo, que se quedaría en una partida de 1
        """
        if len(jugadores) < MIN_PARA_MARCAR:
            raise RepartoImposibleError(
                "Hacen falta al menos dos jugadores para formar una partida."
            )
        signo = -1 if orden == OrdenDeSalida.HIGH_FIRST else 1
        en_orden = sorted(jugadores, key=lambda j: (signo * j.handicap, j.plaza_cogida))
        partidas = []
        inicio = 0
        for tamano in RepartoDePartidas._tamanos(len(jugadores), jugadores_por_partida):
            partidas.append([j.user_id for j in en_orden[inicio : inicio + tamano]])
            inicio += tamano
        return partidas

    @staticmethod
    def _tamanos(jugadores: int, jugadores_por_partida: int) -> list[int]:
        """Llenas salvo la última; si la última fuera de 1, la penúltima cede uno."""
        llenas, resto = divmod(jugadores, jugadores_por_partida)
        tamanos = [jugadores_por_partida] * llenas
        if resto:
            tamanos.append(resto)
        if tamanos and tamanos[-1] == 1:
            tamanos[-2] -= 1
            tamanos[-1] += 1
        return tamanos
