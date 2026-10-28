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
    # «El organizador te ha quitado de X» (release social 2, 27 oct 2026)
    ENROLLMENT_REMOVED = "ENROLLMENT_REMOVED"
    # Inscripcion directa en las publicas (release social 3, 28 oct 2026):
    # «Ana se ha apuntado» para el organizador, «has entrado en la franja de
    # las 9:00» para quien esperaba y «no hubo plaza» al cerrar
    PLAYER_JOINED = "PLAYER_JOINED"
    PLACE_FROM_WAITING_LIST = "PLACE_FROM_WAITING_LIST"
    ENROLLMENT_NO_PLACE = "ENROLLMENT_NO_PLACE"
    # Se borro la franja en cuya espera estaba, la ultima suya, y salio
    TEE_WINDOW_REMOVED = "TEE_WINDOW_REMOVED"
    # Los equipos de la Ryder cambiaron: a cada capitán, que revise su sobre (T4)
    TEAMS_CHANGED = "TEAMS_CHANGED"

    @property
    def is_achievement(self) -> bool:
        """Si es un logro de una vuelta: los de una misma vuelta van en una tarjeta."""
        return self in _ACHIEVEMENTS

    @property
    def is_per_hole(self) -> bool:
        """Si el logro dice en que hoyos fue (`holes`): lo oculto se recuerda por hoyo."""
        return self in _PER_HOLE

    @property
    def is_exclusive_by_date(self) -> bool:
        """
        «Campo nuevo» y «primer torneo»: uno solo por jugador (y campo), en la
        vuelta mas antigua, que pasa de una vuelta a otra al reabrir o al
        cerrarse una anterior (22 oct 2026).
        """
        return self in _EXCLUSIVE_BY_DATE

    @property
    def may_come_from_a_quick_match(self) -> bool:
        """
        Si un evento de este tipo puede salir de una partida rapida: su «como
        acabo» y los logros (que tambien publica un torneo, con
        `from_tournament` en su `payload`).
        """
        return self is ActivityEventType.QUICK_MATCH_FINISHED or self.is_achievement

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

_PER_HOLE = frozenset(
    {ActivityEventType.HOLE_IN_ONE, ActivityEventType.EAGLE_OR_BETTER, ActivityEventType.BIRDIE}
)

_EXCLUSIVE_BY_DATE = frozenset({ActivityEventType.NEW_COURSE, ActivityEventType.FIRST_TOURNAMENT})
