"""
PositionSource Value Object - De dónde sale cada posición del mapa de un hoyo.

Se guarda por posición, no por mapa (BE #532): lo que viene de OpenStreetMap va
bajo su licencia (ODbL) y tiene que poder separarse de lo que es nuestro.
"""

from enum import StrEnum


class PositionSource(StrEnum):
    """
    Origen de una posición del mapa.

    - OSM: importada de OpenStreetMap
    - MANUAL: la puso o corrigió un admin
    - PLAYER: la marcó un jugador y la aprobó un admin
    """

    OSM = "OSM"
    MANUAL = "MANUAL"
    PLAYER = "PLAYER"

    def __str__(self) -> str:
        return self.value
