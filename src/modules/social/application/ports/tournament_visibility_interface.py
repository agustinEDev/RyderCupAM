"""Puerto: que torneos son privados ahora mismo."""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class TournamentVisibilityInterface(ABC):
    """
    Lo que el feed necesita saber de la visibilidad de los torneos.

    Al pasar un torneo a privado se borran sus «X se ha apuntado», pero ese
    borrado puede fallar (solo deja un WARNING). Al leer, el feed y la actividad
    de un perfil preguntan aqui y no enseñan los de un torneo que ahora es
    privado (tabla del 22 oct 2026, E). Es un puerto porque `social` no lee las
    tablas de competicion.
    """

    @abstractmethod
    async def private_ids(self, competition_ids: Sequence[str]) -> set[str]:
        """
        De esos ids, los de los torneos que ahora son privados, en una sola
        lectura. Un id ilegible o de un torneo que ya no existe no cuenta.
        """
