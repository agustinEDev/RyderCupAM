"""
TeeColor Value Object - Color de las barras de salida.

El color, junto al género, identifica la salida. No clasifica por dificultad:
las federaciones no publican categorías, y el reparto de colores varía entre
campos y entre países (en Pebble Beach el oro es de las más largas; en España
va a media tabla).
"""

from enum import StrEnum


class TeeColor(StrEnum):
    """
    Colores de barras de salida.

    La lista sale de los colores realmente usados por los campos federados
    españoles (802 recorridos de la RFEG). El orden es el de frecuencia de uso.

    OTHER cubre las salidas cuyo nombre no es un color, para no forzar datos
    reales dentro de una lista cerrada.
    """

    RED = "RED"
    YELLOW = "YELLOW"
    BLUE = "BLUE"
    WHITE = "WHITE"
    GREEN = "GREEN"
    ORANGE = "ORANGE"
    BLACK = "BLACK"
    PINK = "PINK"
    GOLD = "GOLD"
    OTHER = "OTHER"

    def __str__(self) -> str:
        return self.value
