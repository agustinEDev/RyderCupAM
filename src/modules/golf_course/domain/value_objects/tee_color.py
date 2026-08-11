"""
TeeColor Value Object - Color de las barras de salida.

Es independiente de TeeCategory: el color identifica físicamente la salida en
el campo, mientras que la categoría la clasifica por dificultad. Un mismo color
puede corresponder a categorías distintas según el campo, y hay campos con
varias salidas del mismo color en recorridos diferentes.
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
