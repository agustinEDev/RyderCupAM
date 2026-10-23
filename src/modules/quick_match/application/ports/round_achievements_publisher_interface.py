"""Puerto: publicar en el feed los logros de una vuelta terminada."""

from abc import ABC, abstractmethod


class RoundAchievementsPublisherInterface(ABC):
    """
    Lo que `quick_match` necesita del feed social, sin depender de el.

    El record personal se mide al publicar, con el diferencial de cada vuelta y
    su dia (23 oct 2026): ya no hace falta preguntar nada antes de cerrar.
    """

    @abstractmethod
    async def publish(self, quick_match_id: str) -> int:
        """Publica los logros de la partida y devuelve cuantos creo."""
