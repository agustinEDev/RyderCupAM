"""Puerto: consultar el mejor diferencial de un jugador."""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId


class PlayerDifferentialsInterface(ABC):
    """
    Lo único que el feed necesita saber del WHS: cuál es el mejor diferencial
    de un jugador ahora mismo.

    Se define como puerto en lugar de llamar directamente al caso de uso de
    estadísticas para que el módulo social no dependa del de usuario. El feed no
    sabe calcular un diferencial y no debería: solo necesita compararlos para
    decidir si una vuelta fue un récord.
    """

    @abstractmethod
    async def best_differential(
        self, user_id: UserId, excluding_competition_id: str | None = None
    ) -> float | None:
        """
        El mejor diferencial del jugador, o None si aún no tiene ninguno.

        Con `excluding_competition_id`, sin ninguna vuelta de ese torneo: la
        marca de antes de él (decisión del 22 oct 2026).

        Devuelve None también cuando ninguna de sus vueltas se jugó desde un tee
        conocido: sin Slope ni Course Rating no hay diferencial que calcular.
        """
