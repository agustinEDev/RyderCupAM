"""Puerto: las vueltas en que cada jugador piso un campo."""

from abc import ABC, abstractmethod
from collections.abc import Collection

from src.modules.social.application.exclusive_achievements import PlayedRound
from src.modules.user.domain.value_objects.user_id import UserId

__all__ = ["PlayedRound", "PlayerCourseHistoryInterface"]


class PlayerCourseHistoryInterface(ABC):
    """
    Todo lo que han jugado unos jugadores, de partidas rapidas y de torneos.

    Es un puerto y no una consulta directa porque la respuesta cruza modulos:
    un campo se puede estrenar en una partida rapida o en un torneo, y
    preguntarle solo a uno haria que el mismo campo se estrenara dos veces.
    """

    @abstractmethod
    async def played_rounds(self, user_ids: Collection[UserId]) -> list[PlayedRound]:
        """
        Cada vuelta en la que alguno de ellos jugo al menos un hoyo (la raya
        tambien), sin tope: hasta lo mas antiguo. Con el mismo criterio para
        todas las fuentes (Agustin, 22 oct 2026):

        - partidas rapidas TERMINADAS, tambien las de su papelera;
        - partidos de la Ryder y grupos de stroke play terminados de torneos
          CERRADOS, salvo NO_PRESENTADO.

        Por lotes: un numero fijo de lecturas, crezca o no el numero de
        jugadores, campos o vueltas.
        """
