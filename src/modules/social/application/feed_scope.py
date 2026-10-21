"""
Lo que entra en el feed de un jugador y desde cuando cuenta como novedad.

Vive aparte porque lo comparten el feed y el contador de novedades: el numero
del boton y el de la pantalla tienen que salir de la misma regla, o acabarian
discrepando en cuanto una de las dos cambiara.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
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

# Tope del contador de novedades. El cliente pinta «9+», asi que pasado el 10
# el numero exacto no cambia nada en la pantalla y contarlo seria trabajo tirado
UNSEEN_CAP = 10


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
    """
    async with social_uow:
        amigos = await social_uow.friendships.find_friend_ids(viewer_id)

    publican = []
    async with user_uow:
        for amigo in amigos:
            user = await user_uow.users.find_by_id(amigo)
            if user is not None and user.is_active and user.share_activity:
                publican.append(amigo)
        viewer = await user_uow.users.find_by_id(viewer_id)
        visto_hasta = viewer.feed_last_seen_at if viewer else None

    return FeedScope(
        mine=ActivitySlice(user_ids=(viewer_id,), types=types_seen_by_author()),
        friends=ActivitySlice(
            user_ids=tuple(publican),
            types=types_seen_by_friends(),
            only_visible_to_friends=True,
        ),
        last_seen_at=visto_hasta,
    )


async def count_unseen(social_uow: SocialUnitOfWorkInterface, scope: FeedScope) -> int:
    """
    Cuanto de lo que veria en el feed se ha publicado desde mi ultima visita,
    con el tope de `UNSEEN_CAP`.

    Cuenta **tambien lo propio** (decision de producto, 21 oct 2026): el numero
    anuncia todo lo nuevo de Actividad, y ahi salen tambien los avisos que son
    solo para uno. Sin visita previa, todo lo visible es nuevo.
    """
    async with social_uow:
        return await social_uow.activity_events.count_in(
            scope.slices, since=scope.last_seen_at, cap=UNSEEN_CAP
        )
