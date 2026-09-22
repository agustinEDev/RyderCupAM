"""
SetupMode Value Object - Cuanto monta la aplicacion por su cuenta (FE #695).

Decidido con el dueno del producto el 22 sep, despues de ver lo laboriosa que
es la pantalla de reparto manual: la decision se mueve AL PRINCIPIO. Al crear
el torneo se elige uno de tres modos, y ese modo decide que pasos existen
despues.

- AUTOMATIC: la aplicacion reparte equipos, nombra capitanes (el handicap mas
  bajo de cada equipo) y genera los partidos. Lo unico que pregunta es lo que
  no se puede adivinar: que dias se juega, en que franja y en que campo.
- MANUAL: nada automatico. Equipos, capitanes, rondas, partidos y
  enfrentamientos a mano. Es el camino de hoy, para quien lo quiera.
- RYDER_CUP: la ceremonia. Equipos por draft en directo —opcional, tambien se
  pueden poner a mano—, capitanes nombrados por el organizador, rondas
  configurables y enfrentamientos por sobres.

Es un enum y no dos booleanos porque son tres caminos enteros, no la suma de
dos interruptores: «automatico» y «manual» no son extremos de una misma escala.
"""

from enum import StrEnum


class SetupMode(StrEnum):
    """Cuanto monta la aplicacion por su cuenta."""

    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    RYDER_CUP = "RYDER_CUP"

    def __str__(self) -> str:
        return self.value
