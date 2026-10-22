"""
Lo que entra en el feed de un jugador y desde cuando cuenta como novedad.

Vive aparte porque lo comparten el feed y el contador de novedades: el numero
del boton y el de la pantalla tienen que salir de la misma regla, o acabarian
discrepando en cuanto una de las dos cambiara.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivityEventRepositoryInterface,
    ActivitySlice,
)
from src.modules.social.domain.repositories.friendship_repository_interface import (
    FriendshipRepositoryInterface,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.activity_audience import (
    types_seen_by_author,
    types_seen_by_friends,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.utc_clock import utc_now

# Tope del contador de novedades (tabla del 22 oct 2026, B). Mas alla, el
# numero exacto no cambia nada en la pantalla y contarlo seria trabajo tirado
UNSEEN_CAP = 99

# Cuantas solicitudes de amistad pendientes se leen para el feed. Nadie tiene
# tantas sin responder, y el contador no necesita mas que su tope
MAX_PENDING_REQUESTS = 50


@dataclass(frozen=True)
class FeedScope:
    """Los dos trozos del feed y la ultima visita (None si nunca lo abrio)."""

    mine: ActivitySlice
    friends: ActivitySlice
    last_seen_at: datetime | None

    @property
    def slices(self) -> list[ActivitySlice]:
        return [self.mine, self.friends]


async def resolve_feed_scope(
    social_uow: SocialUnitOfWorkInterface,
    user_uow: UserUnitOfWorkInterface,
    viewer_id: UserId,
    reloj: Callable[[], datetime] = utc_now,
) -> FeedScope:
    """
    Lo mio que veo yo y lo de mis amigos que ven ellos, y cuando mire por
    ultima vez.

    De lo mio, lo SELF y lo BOTH, sin mirar mi `share_activity`: ese
    interruptor gobierna lo que ven los demas, no lo que uno ve de si mismo. De
    mis amigos, solo los que publican, y de ellos lo FRIENDS y lo BOTH que no
    publicaron con la publicacion apagada.

    El amigo con la publicacion apagada se descarta aunque sus eventos ya esten
    ocultos: la regla es "no aparece en el feed de nadie", y no debe depender
    de que otro caso de uso haya hecho bien su parte.

    Las unidades de trabajo se abren en serie, nunca una dentro de otra:
    comparten sesion por debajo, y el `commit` de la interior cerraria la
    transaccion que la exterior todavia esta usando.

    La ultima visita se toma como mucho en el momento actual: una marca vieja
    en hora local de un servidor que no estaba en UTC puede ir horas por
    delante, y sin esto el aviso no contaria nada hasta que el reloj la
    alcanzara.
    """
    async with social_uow:
        amigos = await social_uow.friendships.find_friend_ids(viewer_id)

    # Mis amigos y yo en una sola lectura, no una por amigo
    async with user_uow:
        usuarios = {u.id: u for u in await user_uow.users.find_by_ids([*amigos, viewer_id])}

    publican = [
        amigo
        for amigo in amigos
        if (user := usuarios.get(amigo)) is not None and user.is_active and user.share_activity
    ]
    viewer = usuarios.get(viewer_id)
    visto_hasta = viewer.feed_last_seen_at if viewer else None
    if visto_hasta is not None:
        visto_hasta = min(visto_hasta, reloj())

    return FeedScope(
        mine=ActivitySlice(user_ids=(viewer_id,), types=types_seen_by_author()),
        friends=ActivitySlice(
            user_ids=tuple(publican),
            types=types_seen_by_friends(),
            only_visible_to_friends=True,
        ),
        last_seen_at=visto_hasta,
    )


def payload_for(evento: ActivityEvent, viewer_id: UserId) -> dict:
    """
    El detalle de un evento tal como lo puede ver quien mira.

    El nombre de un invitado (sin cuenta) lo escribio el autor en su partida:
    solo lo ve el. A cualquier otro le llega sin nombre y el cliente pinta «un
    invitado» (revision de BE-2).
    """
    payload = evento.payload
    if evento.user_id == viewer_id:
        return payload
    for clave in ("opponents", "partners"):
        personas = payload.get(clave)
        if isinstance(personas, list):
            payload[clave] = [
                {**p, "name": None} if isinstance(p, dict) and not p.get("user_id") else p
                for p in personas
            ]
    return payload


async def pending_requests(
    friendships: FriendshipRepositoryInterface, viewer_id: UserId
) -> list[Friendship]:
    """
    Las solicitudes de amistad que me han hecho y siguen sin respuesta (F23).

    No son eventos: se leen en vivo de las amistades, asi que aceptarla o
    rechazarla en otro sitio la quita sola (F24), y un bloqueo —que cambia esa
    misma fila— tambien (F25). Solo las recibidas, nunca las enviadas (F26).
    """
    return await friendships.list_pending_received(viewer_id, limit=MAX_PENDING_REQUESTS)


async def count_unseen(
    events: ActivityEventRepositoryInterface,
    scope: FeedScope,
    requests: Sequence[Friendship] = (),
) -> int:
    """
    Cuanto de lo que veria en el feed ha llegado desde mi ultima visita, con el
    tope de `UNSEEN_CAP`: las tarjetas publicadas y las solicitudes de amistad
    recibidas.

    Cuenta **tambien lo propio** (decision de producto, 21 oct 2026): el numero
    anuncia todo lo nuevo de Actividad, y ahi salen tambien los avisos que son
    solo para uno. Sin visita previa, todo lo visible es nuevo.

    Recibe el repositorio y no la unidad de trabajo para contar dentro de la
    misma que ya tenga abierta quien llama.
    """
    # Sin los apuntados a torneos que ahora son privados: el feed no los enseña
    # (regla E), y el numero tiene que decir lo mismo que la pantalla
    # Ni las invitaciones que ya no se pueden aceptar, con el reloj de la propia
    # invitacion (`Invitation.is_expired`, hora local sin zona)
    tarjetas = await events.count_in(
        scope.slices,
        since=scope.last_seen_at,
        cap=UNSEEN_CAP,
        skip_private_enrollments=True,
        open_invitations_at=datetime.now(),
    )
    solicitudes = sum(
        1
        for solicitud in requests
        if scope.last_seen_at is None or solicitud.created_at > scope.last_seen_at
    )
    return min(tarjetas + solicitudes, UNSEEN_CAP)
