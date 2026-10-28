"""Quien ve cada tipo de evento del feed."""

from enum import StrEnum

from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType


class ActivityAudience(StrEnum):
    """
    El publico de un tipo de evento.

    - **SELF**: solo su autor. Avisos que son asunto suyo («tu solicitud se
      cerro sin plaza»): a sus amigos no les dicen nada.
    - **FRIENDS**: solo sus amigos. Lo que cuenta de el a los demas («X se ha
      apuntado a un torneo»); el autor recibe su propio aviso SELF en su lugar.
    - **BOTH**: el autor y sus amigos. Los logros: uno se ve a si mismo en su
      feed —si no, parece que no se guardo— y sus amigos tambien.
    """

    SELF = "SELF"
    FRIENDS = "FRIENDS"
    BOTH = "BOTH"

    @property
    def seen_by_author(self) -> bool:
        return self in (ActivityAudience.SELF, ActivityAudience.BOTH)

    @property
    def seen_by_friends(self) -> bool:
        return self in (ActivityAudience.FRIENDS, ActivityAudience.BOTH)


# El publico de cada tipo. Los seis logros son BOTH: es lo que ya hacia el feed
# (cada uno se ve a si mismo y le ven sus amigos), y el numero de novedades
# cuenta tambien lo propio. Un tipo nuevo tiene que entrar aqui: sin publico no
# se veria en ningun sitio, y un test lo exige
AUDIENCE_BY_TYPE: dict[ActivityEventType, ActivityAudience] = {
    ActivityEventType.HOLE_IN_ONE: ActivityAudience.BOTH,
    ActivityEventType.EAGLE_OR_BETTER: ActivityAudience.BOTH,
    ActivityEventType.BIRDIE: ActivityAudience.BOTH,
    ActivityEventType.NEW_COURSE: ActivityAudience.BOTH,
    ActivityEventType.PERSONAL_BEST: ActivityAudience.BOTH,
    ActivityEventType.FIRST_TOURNAMENT: ActivityAudience.BOTH,
    # Avisos de inscripcion y resultados de torneo: asunto de cada uno
    ActivityEventType.ENROLLMENT_APPROVED: ActivityAudience.SELF,
    ActivityEventType.INVITED_TO_TOURNAMENT: ActivityAudience.SELF,
    ActivityEventType.ENROLLMENT_REQUEST_CLOSED: ActivityAudience.SELF,
    ActivityEventType.ENROLLMENT_REJECTED: ActivityAudience.SELF,
    ActivityEventType.ENROLLMENT_REMOVED: ActivityAudience.SELF,
    ActivityEventType.TOURNAMENT_MATCH_RESULT: ActivityAudience.SELF,
    # Su puesto final lo ven tambien sus amigos (tabla del 27 oct 2026): les
    # abre la clasificacion de una privada
    ActivityEventType.TOURNAMENT_FINAL_STANDING: ActivityAudience.BOTH,
    ActivityEventType.ENROLLMENT_CONFIRMED: ActivityAudience.SELF,
    # «X se ha apuntado a Y»: el autor ya tiene su aviso, o se apunto el
    ActivityEventType.ENROLLED_IN_TOURNAMENT: ActivityAudience.FRIENDS,
    # Como acabo cada uno la partida rapida: uno se ve y le ven sus amigos
    ActivityEventType.QUICK_MATCH_FINISHED: ActivityAudience.BOTH,
    # Tu salida o tu partido: asunto tuyo, aunque el torneo sea publico (G6)
    ActivityEventType.TEE_TIME_ASSIGNED: ActivityAudience.SELF,
}


def audience_of(event_type: ActivityEventType) -> ActivityAudience:
    """El publico de un tipo de evento."""
    return AUDIENCE_BY_TYPE[event_type]


def types_seen_by_author() -> frozenset[ActivityEventType]:
    """Los tipos que el autor ve de si mismo (SELF y BOTH)."""
    return frozenset(t for t, audience in AUDIENCE_BY_TYPE.items() if audience.seen_by_author)


def types_seen_by_friends() -> frozenset[ActivityEventType]:
    """Los tipos que ven sus amigos (FRIENDS y BOTH)."""
    return frozenset(t for t, audience in AUDIENCE_BY_TYPE.items() if audience.seen_by_friends)
