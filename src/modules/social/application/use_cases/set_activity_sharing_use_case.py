"""Caso de Uso: Encender o apagar la publicacion de logros."""

from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.activity_audience import (
    types_seen_by_author,
    types_seen_by_friends,
)
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SetActivitySharingUseCase:
    """
    El jugador decide si sus logros se publican en el feed de sus amigos.

    **Apagarlo retira de los amigos lo ya publicado**, no solo deja de generar.
    Es la parte que importa: quien apaga esto casi siempre quiere que lo suyo
    deje de verse, no que se congele donde estaba.

    Pero solo de los amigos (decidido con Agustin el 21 oct 2026): lo que era
    solo para ellos (FRIENDS) se borra, y lo que tambien ve el autor (BOTH) se
    le oculta a ellos y se le queda a el. Lo SELF no se toca. Mientras siga
    apagado, lo nuevo se publica igual, pero oculto.

    Volver a encenderlo **no destapa nada**: lo retirado o publicado a oscuras
    sigue siendo solo del autor, y sus amigos ven lo que se publique a partir
    de ahi.
    """

    def __init__(
        self,
        user_uow: UserUnitOfWorkInterface,
        social_uow: SocialUnitOfWorkInterface,
    ):
        self._user_uow = user_uow
        self._social_uow = social_uow

    async def execute(self, user_id_raw: str, enabled: bool) -> int:
        """
        Cambia el interruptor y devuelve cuantos eventos se retiraron de los
        amigos, borrados u ocultos.

        Devuelve 0 al encender: encender no borra ni destapa nada.
        """
        user_id = UserId(user_id_raw)

        async with self._user_uow:
            user = await self._user_uow.users.find_by_id(user_id)
            if user is None:
                raise UserNotFoundError(f"User not found: {user_id_raw}")

            user.set_activity_sharing(enabled)
            await self._user_uow.users.save(user)

        if enabled:
            return 0

        # Se borra despues de guardar el interruptor: si fallara entre medias,
        # es preferible haber dejado de publicar con el historial aun visible
        # que seguir publicando con el historial ya borrado
        solo_amigos = types_seen_by_friends() - types_seen_by_author()
        de_ambos = types_seen_by_friends() & types_seen_by_author()
        async with self._social_uow:
            borrados = await self._social_uow.activity_events.delete_for_user(user_id, solo_amigos)
            ocultos = await self._social_uow.activity_events.hide_from_friends(user_id, de_ambos)
        return borrados + ocultos
