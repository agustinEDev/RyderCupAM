"""El ultimo paso antes de guardar los logros de una publicacion."""

from datetime import datetime

from src.modules.social.application.exclusive_achievements import utc_naive
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.shared.domain.utc_clock import utc_now


async def stamp_for_publication(
    user_uow: UserUnitOfWorkInterface,
    eventos: list[ActivityEvent],
    published_at: datetime | None = None,
) -> list[ActivityEvent]:
    """
    Los eventos listos para guardar: con una misma fecha de publicacion y con
    la visibilidad que manda el interruptor **ahora**.

    **Una sola fecha para toda la publicacion.** Los logros de una vuelta se
    publican juntos, y el cursor del feed desempata por id entre los que
    comparten fecha: con una por evento, el orden dependeria de microsegundos.

    **El interruptor se vuelve a leer justo antes de guardar.** Entre leer la
    partida y guardar sus logros se juzga cada vuelta, y eso tarda: si el
    jugador apaga la publicacion en ese rato, sus logros no pueden salir
    visibles. Basta con que uno de los dos momentos lo tenga apagado.

    **Lo que ya se publico oculto no se destapa**, aunque ahora este encendido:
    eso lo pone el repositorio al guardar, que sabe que estaba oculto (el
    logro, o el apunte que dejo al retirarlo). Aqui solo se oculta, nunca se
    destapa.

    **La fecha es la de ahora**, salvo que llegue otra: la partida rapida que
    se cierra sola sale el dia que se jugo, no arriba con «ahora» (Agustin,
    24 oct 2026).
    """
    if not eventos:
        return []

    publicado = utc_now() if published_at is None else utc_naive(published_at)
    async with user_uow:
        usuarios = {
            u.id: u for u in await user_uow.users.find_by_ids(list({e.user_id for e in eventos}))
        }

    def _publica_ahora(evento: ActivityEvent) -> bool:
        user = usuarios.get(evento.user_id)
        return user is not None and user.share_activity

    return [
        ActivityEvent.reconstruct(
            id=evento.id,
            user_id=evento.user_id,
            type=evento.type,
            occurred_at=evento.occurred_at,
            source_match_id=evento.source_match_id,
            payload=evento.payload,
            published_at=publicado,
            visible_to_friends=evento.visible_to_friends and _publica_ahora(evento),
        )
        for evento in eventos
    ]
