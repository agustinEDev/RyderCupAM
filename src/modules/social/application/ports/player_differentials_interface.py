"""Puerto: consultar los diferenciales de un jugador."""

from abc import ABC, abstractmethod

from src.modules.social.domain.services.personal_best import DatedDifferential
from src.modules.user.domain.value_objects.user_id import UserId


class PlayerDifferentialsInterface(ABC):
    """
    Lo único que el feed necesita saber del WHS: el diferencial de cada vuelta
    del jugador, con su día y de dónde sale.

    Se define como puerto en lugar de llamar directamente al caso de uso de
    estadísticas para que el módulo social no dependa del de usuario. El feed no
    sabe calcular un diferencial y no debería: solo necesita compararlos para
    decidir si una vuelta fue un récord (`record_context`).
    """

    @abstractmethod
    async def round_differentials(self, user_id: UserId) -> list[DatedDifferential]:
        """
        Las vueltas computables del jugador que tienen diferencial, de la más
        reciente a la más antigua. Las que se jugaron sin un tee conocido no
        están: sin Slope ni Course Rating no hay diferencial que calcular.
        """
