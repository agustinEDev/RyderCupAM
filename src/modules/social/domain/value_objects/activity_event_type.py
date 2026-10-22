"""Tipos de evento que se publican en el feed de los amigos."""

from enum import StrEnum


class ActivityEventType(StrEnum):
    """
    Lo que se publica en el feed.

    **Los seis primeros son logros, no actividad.** La diferencia no es de
    matiz: un birdie apetece enseñarlo, y "jugó 108 golpes el martes" no.
    Publicar lo segundo empujaría a la gente a no anotar sus vueltas malas, que
    es justo el sesgo que las estadísticas ya sufren (BE #173).

    **Los demás son avisos** (BE-2, tabla aprobada el 21 oct 2026): de tu
    inscripción y tus resultados (solo tuyos), de que un amigo se apunta a un
    torneo público y de cómo acabó cada uno una partida rápida. Esta última sí
    cuenta una vuelta mala —el último puesto sale— por decisión expresa de
    producto: las partidas rápidas de los amigos, todas, con puesto y puntos.

    Cada tipo nuevo es una decisión de producto y necesita su público en
    `AUDIENCE_BY_TYPE`.
    """

    HOLE_IN_ONE = "HOLE_IN_ONE"
    EAGLE_OR_BETTER = "EAGLE_OR_BETTER"
    BIRDIE = "BIRDIE"
    NEW_COURSE = "NEW_COURSE"
    PERSONAL_BEST = "PERSONAL_BEST"
    FIRST_TOURNAMENT = "FIRST_TOURNAMENT"

    # Avisos de BE-2. Caben en la columna (VARCHAR 30) sin migracion
    ENROLLMENT_APPROVED = "ENROLLMENT_APPROVED"
    INVITED_TO_TOURNAMENT = "INVITED_TO_TOURNAMENT"
    ENROLLMENT_REQUEST_CLOSED = "ENROLLMENT_REQUEST_CLOSED"
    ENROLLMENT_REJECTED = "ENROLLMENT_REJECTED"
    ENROLLED_IN_TOURNAMENT = "ENROLLED_IN_TOURNAMENT"
    TOURNAMENT_MATCH_RESULT = "TOURNAMENT_MATCH_RESULT"
    TOURNAMENT_FINAL_STANDING = "TOURNAMENT_FINAL_STANDING"
    QUICK_MATCH_FINISHED = "QUICK_MATCH_FINISHED"
    # «Ya estás inscrito»: entraste sin solicitud, aceptando una invitacion o
    # inscrito por el organizador (tabla del 22 oct 2026, C)
    ENROLLMENT_CONFIRMED = "ENROLLMENT_CONFIRMED"
    # Tu salida o tu partido en una ronda de torneo (G, tabla del 22 oct 2026)
    TEE_TIME_ASSIGNED = "TEE_TIME_ASSIGNED"

    @property
    def is_achievement(self) -> bool:
        """Si es un logro de una vuelta: los de una misma vuelta van en una tarjeta."""
        return self in _ACHIEVEMENTS

    @classmethod
    def from_string(cls, value: str) -> "ActivityEventType":
        try:
            return cls(value)
        except ValueError as error:
            raise ValueError(f"Unknown activity event type: {value}") from error


_ACHIEVEMENTS = frozenset(
    {
        ActivityEventType.HOLE_IN_ONE,
        ActivityEventType.EAGLE_OR_BETTER,
        ActivityEventType.BIRDIE,
        ActivityEventType.NEW_COURSE,
        ActivityEventType.PERSONAL_BEST,
        ActivityEventType.FIRST_TOURNAMENT,
    }
)
