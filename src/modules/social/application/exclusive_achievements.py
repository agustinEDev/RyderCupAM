"""
Logros exclusivos por fecha real (decision de Agustin, 22 oct 2026).

«Campo nuevo» es SIEMPRE de la vuelta mas antigua del jugador en ese campo,
sea de un torneo o una partida rapida; «primer torneo», SIEMPRE de su torneo
mas antiguo. Cada uno lleva en el `payload` cuando se jugo (`played_at`, UTC
ISO) y con eso se compara lo publicado sin mas consultas:

- si ya hay uno publicado ANTERIOR, el nuevo no sale;
- si los que hay son POSTERIORES, se retiran y sale el nuevo.

Asi el estado final no depende del orden de cierre, del dia ni del origen.
Solo cuenta lo publicado: lo que sigue en juego no ha publicado nada, y lo que
se cancela nunca lo hara.

Que vuelta es la mas antigua lo dice el historial (`PlayedRound`), con UN solo
criterio de «jugo» para el historial y para quien publica (Agustin, 22 oct):
pisaste el campo si jugaste al menos un hoyo, sea o no una vuelta computable
para los demas logros (un 4&3, una retirada con hoyos, una partida rapida de
12 hoyos). No cuentan los no presentados, las vueltas sin hoyos, los torneos
sin cerrar ni las partidas rapidas sin terminar.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from src.modules.competition.domain.services.scoring_opening_service import (
    OPENING_HOUR_BY_SESSION,
)
from src.modules.competition.domain.services.zona_horaria import zona_del_campo
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
)
from src.modules.social.domain.services.withdrawn_achievement import scope_of
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.user.domain.value_objects.user_id import UserId

EXCLUSIVE_TYPES = frozenset(t for t in ActivityEventType if t.is_exclusive_by_date)

# La clave del payload con el instante en que se jugo
PLAYED_AT = "played_at"

# Una sesion que no se conoce, a mediodia: el mismo criterio que la fecha de la
# ronda en el feed
_HORA_SIN_SESION = 12

# Cuando se jugo, y el desempate con el mismo instante: el torneo (o la
# partida rapida) y despues el origen. Que el torneo vaya antes que el grupo
# hace que dos torneos en la misma sesion den los dos logros al mismo
PlayedKey = tuple[datetime, str, str]


def round_instant(
    round_date: date, session_type: SessionType | None, timezone: str | None
) -> datetime:
    """
    Cuando se jugo una ronda de torneo, en UTC y sin zona: la hora a la que abre
    su sesion (6, 12 o 18 locales) en la zona del campo, la misma que usa la
    anotacion. Una ronda sin sesion, a mediodia local.

    Sin zona (decision de este arreglo, 22 oct 2026): el dia y esa hora local
    tomados como UTC. Ordena bien las sesiones del mismo campo, que comparten
    zona, y frente a una partida rapida se equivoca como mucho en el desfase.
    """
    hora = (
        OPENING_HOUR_BY_SESSION.get(session_type, _HORA_SIN_SESION)
        if session_type is not None
        else _HORA_SIN_SESION
    )
    local = datetime.combine(round_date, time(hora))
    zona = zona_del_campo(timezone)
    if zona is None:
        return local
    return local.replace(tzinfo=zona).astimezone(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class PlayedRound:
    """
    Una vuelta en la que el jugador piso un campo (al menos un hoyo jugado).

    - `instant`: en UTC y sin zona; una ronda de torneo, `round_instant`; una
      partida rapida, su creacion.
    - `source_id`: el partido de la Ryder, el grupo de stroke play o la partida
      rapida; `competition_id`, el torneo, o None si es una partida rapida.
    - `kind`: MATCH, TEE_GROUP o QUICK_MATCH. `player_ids`: quienes jugaron ese
      partido o grupo, para que el logro abra su tarjeta.
    - `round_date`: el dia de la ronda de torneo (fecha del logro en el feed).
    """

    user_id: UserId
    golf_course_id: str
    instant: datetime
    source_id: str
    holes_played: int
    competition_id: str | None = None
    kind: str = "QUICK_MATCH"
    player_ids: tuple[str, ...] = ()
    round_date: date | None = None

    @property
    def key(self) -> "PlayedKey":
        """La misma clave con la que se comparan los logros publicados (`event_key`)."""
        return played_key(self.instant, self.competition_id, self.source_id)


def first_on_each_course(rondas: Iterable[PlayedRound]) -> dict[tuple[UserId, str], PlayedRound]:
    """Por jugador y campo, la primera vez que lo piso: su «campo nuevo»."""
    primeras: dict[tuple[UserId, str], PlayedRound] = {}
    for ronda in rondas:
        clave = (ronda.user_id, ronda.golf_course_id)
        if clave not in primeras or ronda.key < primeras[clave].key:
            primeras[clave] = ronda
    return primeras


def first_tournament_of_each(rondas: Iterable[PlayedRound]) -> dict[UserId, PlayedRound]:
    """Por jugador, su primera vuelta de torneo: de ella cuelga su «primer torneo»."""
    primeras: dict[UserId, PlayedRound] = {}
    for ronda in rondas:
        if ronda.competition_id is None:
            continue
        if ronda.user_id not in primeras or ronda.key < primeras[ronda.user_id].key:
            primeras[ronda.user_id] = ronda
    return primeras


def utc_naive(instante: datetime) -> datetime:
    """En UTC y sin zona, como el resto de fechas que se guardan: las que no tienen zona ya lo son."""
    if instante.tzinfo is None:
        return instante
    return instante.astimezone(UTC).replace(tzinfo=None)


def as_iso(instante: datetime) -> str:
    """El instante para el payload: UTC ISO con «Z»."""
    return utc_naive(instante).isoformat() + "Z"


def played_key(instante: datetime, competition_id: str | None, source_id: str) -> PlayedKey:
    """La clave con la que se ordenan las vueltas: la misma al publicar y al leer el historial."""
    return utc_naive(instante), competition_id or source_id, source_id


def event_key(evento: ActivityEvent) -> PlayedKey:
    """
    La clave de un logro publicado. Uno de antes de llevar `played_at` se
    compara por su `occurred_at` (la fecha de la ronda a mediodia o la creacion
    de la partida rapida).
    """
    crudo = evento.payload.get(PLAYED_AT)
    instante = evento.occurred_at
    if isinstance(crudo, str):
        try:
            instante = datetime.fromisoformat(crudo.removesuffix("Z"))
        except ValueError:
            instante = evento.occurred_at
    return played_key(instante, evento.payload.get("competition_id"), evento.source_match_id)


def player_scope(user_id: UserId) -> str:
    """El candado de un jugador: no choca con el de un torneo, que es su id a secas."""
    return f"player:{user_id.value}"


async def lock_players(repo: ActivityEventRepositoryInterface, user_ids) -> None:
    """
    Bloquea a esos jugadores hasta el final de la transaccion, SIEMPRE en el
    mismo orden: dos publicaciones que comparten jugadores no se cruzan. El
    candado de un torneo se toma antes que estos, y nadie toma el de un torneo
    con el de un jugador ya cogido, asi que no hay ciclos.
    """
    for user_id in sorted(set(user_ids), key=lambda u: str(u.value)):
        await repo.lock_scope(player_scope(user_id))


async def keep_only_the_oldest(
    repo: ActivityEventRepositoryInterface,
    events: Sequence[ActivityEvent],
    is_own: Callable[[ActivityEvent], bool],
) -> list[ActivityEvent]:
    """
    Lo que queda por publicar de `events` tras aplicar la regla, y retira lo
    publicado que sobra. Quien llama ya tiene los candados de los jugadores.

    `is_own` dice que logros publicados son de la misma publicacion (el mismo
    torneo o la misma partida rapida): esos los sustituye quien llama, no
    cuentan como otros.

    En cada ambito gana el mas antiguo entre los publicados y el nuevo; los
    demas publicados se retiran, tambien un doble que quedara de antes.
    """
    candidatos = [e for e in events if e.type in EXCLUSIVE_TYPES]
    if not candidatos:
        return list(events)

    usuarios = list({e.user_id for e in candidatos})
    publicados: dict[tuple, list[ActivityEvent]] = {}
    for evento in await repo.find_for_users(usuarios, EXCLUSIVE_TYPES):
        if not is_own(evento):
            publicados.setdefault(scope_of(evento), []).append(evento)

    descartados: set[int] = set()
    retirar: dict[ActivityEventType, set[tuple[UserId, str]]] = {}
    for candidato in candidatos:
        otros = publicados.get(scope_of(candidato), [])
        ganador = min([candidato, *otros], key=event_key)
        if ganador is not candidato:
            descartados.add(id(candidato))
        for otro in otros:
            if otro is not ganador:
                retirar.setdefault(otro.type, set()).add((otro.user_id, otro.source_match_id))

    for tipo, parejas in retirar.items():
        await repo.delete_pairs(tipo, sorted(parejas, key=lambda p: (str(p[0].value), p[1])))
    return [e for e in events if id(e) not in descartados]
