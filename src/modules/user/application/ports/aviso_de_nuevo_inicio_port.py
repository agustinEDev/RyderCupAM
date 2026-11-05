"""El puerto del aviso de «nuevo inicio de sesión» (BE #737)."""

from typing import Protocol

from src.modules.user.application.dto.device_dto import AvisoDeNuevoInicioRequestDTO


class IAvisoDeNuevoInicio(Protocol):
    """Quien avisa al usuario de que se ha entrado desde un dispositivo nuevo.

    El login no espera al correo: la implementación de la API lo manda en segundo
    plano. Nunca lanza.
    """

    async def avisa(self, request: AvisoDeNuevoInicioRequestDTO) -> None:
        """Avisa, si toca, del inicio de sesión desde `request.device_id`."""
        ...
