"""
HojaDeSalidas - Las salidas de una franja de stroke play (#251).

Decidido con Agustín el 6-7 oct 2026. Una franja (la sesión de la Ryder) tiene:

- **Primera y última salida**: la hora final ES la última salida posible, así
  que 15:00-18:00 cada 10 minutos son 19 salidas.
- **Intervalo** entre salidas, de 5 a 20 minutos.
- **Jugadores por partida**, 3 o 4.

El cupo de la franja sale de ahí (salidas por jugadores por partida), no se
escribe: así no puede contradecirse con la hoja (decisión 5 de la #251).
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from functools import cached_property

INTERVALO_MINIMO = 5
INTERVALO_MAXIMO = 20
JUGADORES_POR_PARTIDA = (3, 4)


class HojaDeSalidasInvalidaError(ValueError):
    """La hoja de salidas no es posible."""


@dataclass(frozen=True)
class HojaDeSalidas:
    """Primera y última salida, intervalo y jugadores por partida de una franja."""

    primera_salida: time
    ultima_salida: time
    intervalo_minutos: int
    jugadores_por_partida: int

    def __post_init__(self) -> None:
        for hora in (self.primera_salida, self.ultima_salida):
            if hora.second or hora.microsecond or hora.tzinfo is not None:
                raise HojaDeSalidasInvalidaError(
                    "Las horas de salida van en HH:MM, hora del campo, sin segundos ni huso."
                )
        if self.ultima_salida < self.primera_salida:
            raise HojaDeSalidasInvalidaError("La última salida no puede ser anterior a la primera.")
        if not INTERVALO_MINIMO <= self.intervalo_minutos <= INTERVALO_MAXIMO:
            raise HojaDeSalidasInvalidaError(
                f"El intervalo entre salidas va entre {INTERVALO_MINIMO} y "
                f"{INTERVALO_MAXIMO} minutos."
            )
        if self.jugadores_por_partida not in JUGADORES_POR_PARTIDA:
            raise HojaDeSalidasInvalidaError("Las partidas son de 3 o 4 jugadores.")

    @cached_property
    def salidas(self) -> list[time]:
        """Cada hora de salida, de la primera a la última que cabe (se calcula una vez)."""
        dia = datetime(2000, 1, 1)
        hora = datetime.combine(dia, self.primera_salida)
        fin = datetime.combine(dia, self.ultima_salida)
        paso = timedelta(minutes=self.intervalo_minutos)
        horas = []
        while hora <= fin:
            horas.append(hora.time())
            hora += paso
        return horas

    @property
    def numero_de_salidas(self) -> int:
        """Cuántas salidas hay en la franja."""
        return len(self.salidas)

    @property
    def cupo(self) -> int:
        """Cuántos jugadores caben: salidas por jugadores por partida."""
        return self.numero_de_salidas * self.jugadores_por_partida

    def se_solapa_con(self, otra: "HojaDeSalidas") -> bool:
        """Si comparten alguna hora, también si una acaba justo cuando empieza la otra."""
        return (
            self.primera_salida <= otra.ultima_salida and otra.primera_salida <= self.ultima_salida
        )
