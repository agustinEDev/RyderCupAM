"""El puerto de «la RFEG ha encontrado su hándicap» (D1 y D4, 16 nov 2026)."""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId


class IHandicapEncontradoEnLaRfeg(ABC):
    """
    Quien se entera de que la RFEG dio el hándicap de un jugador fuera de una
    actualización de competición: desde su perfil o al entrar.

    Las competiciones cerradas donde juega lo cuentan como actualizado con la
    RFEG y, en un stroke play sin empezar, corrigen su hándicap fijado. Un
    hándicap puesto a mano no llega aquí. Se llama con el hándicap ya guardado.
    """

    @abstractmethod
    async def encontrado(self, user_id: UserId, handicap: float) -> None:
        """La RFEG dio `handicap` para `user_id`, y ya está guardado en su perfil."""
