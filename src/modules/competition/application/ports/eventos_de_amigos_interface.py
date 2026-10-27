"""Puerto: los amigos con un evento de una competición en la Actividad de quien mira."""

from abc import ABC, abstractmethod

from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class EventosDeAmigosInterface(ABC):
    """
    La llave de una privada (tabla del 27 oct 2026): quien está fuera ve la
    clasificación y la partida de un amigo si en SU Actividad le sale un evento
    de ese amigo en esa competición. La Actividad la lleva el módulo social.
    """

    @abstractmethod
    async def amigos_con_evento_en(
        self, user_id: UserId, competition_id: CompetitionId
    ) -> frozenset[UserId]:
        """Sus amigos con algún evento de esa competición que le sale en Actividad."""
