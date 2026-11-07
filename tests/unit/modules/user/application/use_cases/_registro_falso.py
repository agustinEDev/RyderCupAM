"""
Un RegisterDeviceUseCase de mentira que da de alta un dispositivo de verdad (BE #737).

Desde BE #737 toda sesión registra su dispositivo, también sin User-Agent, y el
token lleva su id: un mock que devuelve otro mock como respuesta ya no vale.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

from src.modules.user.application.dto.device_dto import RegisterDeviceResponseDTO


def registro_de_dispositivo_falso(device_id: str | None = None) -> AsyncMock:
    """El registro de dispositivos, con una respuesta válida."""
    registro = AsyncMock()
    registro.execute.return_value = RegisterDeviceResponseDTO(
        device_id=device_id or str(uuid4()),
        is_new_device=False,
        message="Dispositivo actualizado",
    )
    return registro
