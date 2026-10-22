"""Puerto: publicar en el feed los logros de un torneo terminado."""

from abc import ABC, abstractmethod


class TournamentAchievementsPublisherInterface(ABC):
    """
    Lo que `competition` necesita del feed social, sin depender de el.

    Una sola operacion: el record personal se mide contra la marca de ANTES del
    torneo, que el feed calcula sin ninguna de sus vueltas (decision del 22 oct
    2026). Ya no hace falta preguntar nada antes de cerrar, y por eso sirve
    tambien al volver a cerrar un torneo reabierto.
    """

    @abstractmethod
    async def publish(self, competition_id: str) -> int:
        """Publica los logros del torneo y devuelve cuantos creo."""
