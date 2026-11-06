"""El puerto del aviso de «intentos fallidos» (BE #732)."""

from abc import ABC, abstractmethod

from src.modules.user.application.dto.user_dto import AvisoDeFallosRequestDTO


class IAvisoDeFallos(ABC):
    """Quien avisa al dueño de que alguien está fallando su contraseña.

    El login no espera al correo: la implementación de la API lo manda en segundo
    plano. Nunca lanza.
    """

    @abstractmethod
    async def avisa(self, request: AvisoDeFallosRequestDTO) -> None:
        """Avisa, si toca, de que una red quedó bloqueada o saltó el respaldo."""
