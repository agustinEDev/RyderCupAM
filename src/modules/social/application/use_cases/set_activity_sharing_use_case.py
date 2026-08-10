"""Caso de Uso: Encender o apagar la publicacion de logros."""

from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SetActivitySharingUseCase:
    """
    El jugador decide si sus logros se publican en el feed de sus amigos.

    **Apagarlo retira lo ya publicado**, no solo deja de generar. Es la parte que
    importa: quien apaga esto casi siempre quiere que lo suyo deje de verse, no
    que se congele donde estaba. Dejar el historial visible seria cumplir la
    letra de la peticion y no lo que se estaba pidiendo.

    Volver a encenderlo **no recupera nada**: los eventos borrados no vuelven, y
    el feed se llena otra vez con las vueltas que se jueguen a partir de ahi.
    Guardar lo retirado por si acaso significaria conservar justo lo que el
    jugador pidio quitar.
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
        Cambia el interruptor y devuelve cuantos eventos se retiraron.

        Devuelve 0 al encender: encender no borra nada.
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
        async with self._social_uow:
            return await self._social_uow.activity_events.delete_for_user(user_id)
