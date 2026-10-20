"""
Modality Value Object - La modalidad de juego: cómo se gana (RyderCupAM#251, #470).

Decidido con el dueño del producto el 1 oct 2026: la modalidad es el primer
nivel y, dentro de ella, el tipo de torneo. Es compartida porque la usan la
competición (que guarda su tipo, y de él sale la modalidad) y la partida rápida.

- MATCH_PLAY: hoyo a hoyo contra un rival; gana quien gana más hoyos.
- STROKE_PLAY: por el total de la vuelta, en golpes (Medal) o en puntos
  (Stableford).
"""

from enum import StrEnum


class Modality(StrEnum):
    """Cómo se gana: hoyo a hoyo o por el total."""

    MATCH_PLAY = "MATCH_PLAY"
    STROKE_PLAY = "STROKE_PLAY"

    def __str__(self) -> str:
        return self.value
