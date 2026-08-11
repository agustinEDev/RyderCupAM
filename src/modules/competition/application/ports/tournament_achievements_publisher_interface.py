"""Puerto: publicar en el feed los logros de un torneo terminado."""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId


class TournamentAchievementsPublisherInterface(ABC):
    """
    Lo que `competition` necesita del feed social, sin depender de el.

    Igual que en las partidas rapidas, son dos operaciones porque el record
    personal solo se puede medir a caballo del cierre: **antes** se pregunta cual
    era el mejor diferencial de cada jugador y **despues** se compara. Una vez
    cerrado el torneo, esas vueltas ya cuentan para sus estadisticas.
    """

    @abstractmethod
    async def capture_best_differentials(
        self, user_ids: list[UserId]
    ) -> dict[str, float | None]:
        """El mejor diferencial de cada jugador antes de cerrar el torneo."""

    @abstractmethod
    async def publish(
        self, competition_id: str, best_differential_before: dict[str, float | None]
    ) -> int:
        """Publica los logros del torneo y devuelve cuantos creo."""
