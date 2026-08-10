"""Caso de Uso: Dar el feed por visto."""

from datetime import datetime

from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class MarkFeedAsSeenUseCase:
    """
    Apaga el aviso de novedades del feed.

    Es una llamada aparte y no un efecto de leer el feed porque son dos
    intenciones distintas: cargar la primera pagina no significa haber visto lo
    que hay: el cliente pide el feed tambien para refrescarlo en segundo plano,
    y marcarlo ahi apagaria el aviso sin que nadie lo hubiera mirado.

    Guarda **el momento de la llamada** y no la fecha del ultimo evento
    devuelto: lo que se publique mientras el jugador lee vuelve a contar como
    novedad, que es lo que se espera de un aviso.

    Usa `datetime.now()` y no UTC porque esta fecha se compara con el
    `occurred_at` de los eventos, que sale del `created_at` de la partida, y ese
    lo escribe el dominio con `datetime.now()`. Con UTC quedaria desplazada las
    horas que separen al servidor de UTC, y los logros publicados en esa
    ventana contarian como no vistos para siempre: el aviso no se apagaria nunca
    del todo.
    """

    def __init__(self, user_uow: UserUnitOfWorkInterface):
        self._user_uow = user_uow

    async def execute(self, user_id_raw: str) -> datetime:
        """Marca el feed como visto y devuelve el momento registrado."""
        user_id = UserId(user_id_raw)
        visto_en = datetime.now()

        async with self._user_uow:
            user = await self._user_uow.users.find_by_id(user_id)
            if user is None:
                raise UserNotFoundError(f"User not found: {user_id_raw}")

            user.mark_feed_as_seen(visto_en)
            await self._user_uow.users.save(user)

        return visto_en
