"""Puerto: los amigos de un jugador, para saber a quién ve de una competición."""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId


class AmigosInterface(ABC):
    """
    Los amigos los lleva el módulo social; aquí solo se pregunta por ellos
    (release social 2, 27 oct 2026): antes de publicarse una competición, cada
    uno ve de los inscritos solo a sus amigos.
    """

    @abstractmethod
    async def ids_de_los_amigos(self, user_id: UserId) -> frozenset[UserId]:
        """Los ids de sus amistades aceptadas; ni las pendientes ni los bloqueos."""
