"""Tipos de evento que se publican en el feed de los amigos."""

from enum import Enum


class ActivityEventType(str, Enum):
    """
    Lo que se publica en el feed.

    **Son logros, no actividad.** La diferencia no es de matiz: un birdie
    apetece enseñarlo, y "jugó 108 golpes el martes" no. Publicar lo segundo
    empujaría a la gente a no anotar sus vueltas malas, que es justo el sesgo
    que las estadísticas ya sufren (BE #173) y que no conviene alimentar desde
    otro sitio.

    De ahí que aquí no haya ningún `ROUND_PLAYED` ni nada que delate una vuelta
    mala. Todo lo que entre en esta lista tiene que ser algo que el propio
    jugador enseñaría.
    """

    HOLE_IN_ONE = "HOLE_IN_ONE"
    EAGLE_OR_BETTER = "EAGLE_OR_BETTER"
    BIRDIE = "BIRDIE"
    NEW_COURSE = "NEW_COURSE"
    PERSONAL_BEST = "PERSONAL_BEST"
    FIRST_TOURNAMENT = "FIRST_TOURNAMENT"

    @classmethod
    def from_string(cls, value: str) -> "ActivityEventType":
        try:
            return cls(value)
        except ValueError as error:
            raise ValueError(f"Unknown activity event type: {value}") from error
