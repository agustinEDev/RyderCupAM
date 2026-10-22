"""Puerto: que partidas rapidas tiene cada autor en su papelera."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.modules.user.domain.value_objects.user_id import UserId


class QuickMatchTrashInterface(ABC):
    """
    Lo que el feed necesita saber de la papelera de partidas rapidas.

    Si el autor manda una partida rapida a su papelera, sus amigos dejan de ver
    en Actividad lo que salio de ella —el «como acabo» y sus logros— y lo
    vuelven a ver si la saca (prueba de punta a punta, 22 oct 2026). La
    papelera es de cada uno: la de otro jugador de la partida no oculta lo del
    autor. Es un puerto porque `social` no lee las tablas de partidas rapidas.
    """

    @abstractmethod
    async def trashed_by_author(
        self, pairs: Sequence[tuple[str, UserId]]
    ) -> set[tuple[str, UserId]]:
        """
        De esas parejas (partida, autor), las de partidas rapidas que ese autor
        tiene ahora en su papelera, en una sola lectura. Un id ilegible o que no
        es de una partida rapida no cuenta.
        """
