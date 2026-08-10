"""Puerto: publicar en el feed los logros de una vuelta terminada."""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId


class RoundAchievementsPublisherInterface(ABC):
    """
    Lo que `quick_match` necesita del feed social, sin depender de el.

    Son dos operaciones y no una porque el record personal solo se puede medir a
    caballo del cierre: **antes** de cerrar la partida se pregunta cual era el
    mejor diferencial del jugador, y **despues** se compara. Una vez cerrada, esa
    vuelta ya cuenta para sus estadisticas y no hay forma de preguntar como
    estaba el registro sin ella.
    """

    @abstractmethod
    async def capture_best_differentials(
        self, user_ids: list[UserId]
    ) -> dict[str, float | None]:
        """El mejor diferencial de cada jugador antes de cerrar la vuelta."""

    @abstractmethod
    async def publish(
        self, quick_match_id: str, best_differential_before: dict[str, float | None]
    ) -> int:
        """Publica los logros de la partida y devuelve cuantos creo."""
