"""El puerto del aviso de «sesión cerrada por seguridad» (F-02)."""

from abc import ABC, abstractmethod

from src.modules.user.application.dto.device_dto import AvisoDeSesionCerradaRequestDTO


class IAvisoDeSesionCerrada(ABC):
    """Quien avisa al usuario de que cerramos la sesión de un dispositivo por un robo.

    El refresco no espera al correo: la implementación de la API lo manda en segundo
    plano. Nunca lanza.
    """

    @abstractmethod
    async def avisa(self, request: AvisoDeSesionCerradaRequestDTO) -> None:
        """Avisa, si toca, de que se cerró la sesión de `request.device_id`."""
