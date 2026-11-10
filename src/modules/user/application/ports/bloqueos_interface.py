"""Puerto: quién bloqueó a quién, para el avatar y el autocompletado (F-09)."""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId


class BloqueosInterface(ABC):
    """
    Los bloqueos los lleva el módulo social; aquí solo se pregunta por ellos
    (fase 3 del plan a 9, 10 nov 2026). Quien me bloqueó no existe para mí: ni su
    avatar ni encontrarle al buscar. Si lo bloqueé yo, todo como antes.
    """

    @abstractmethod
    async def me_bloqueo(self, quien_mira: UserId, otro: UserId) -> bool:
        """Si `otro` bloqueó a `quien_mira` (no al revés)."""

    @abstractmethod
    async def quienes_me_bloquearon(self, quien_mira: UserId) -> frozenset[UserId]:
        """Los ids de quienes bloquearon a `quien_mira`, en una sola lectura."""
