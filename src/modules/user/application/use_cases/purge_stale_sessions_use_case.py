"""
La limpieza de dispositivos y refrescos viejos (BE #737).

Hasta ahora no se borraba nada: en producción una cuenta tenía 193 dispositivos
(191 revocados) y 750 de 761 refrescos estaban caducados. Se guardaban para
siempre la IP y el navegador de cada uno, contra la minimización de datos (RGPD).
"""

from datetime import timedelta

from src.modules.user.application.dto.device_dto import (
    PurgeStaleSessionsRequestDTO,
    PurgeStaleSessionsResponseDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)

# Un dispositivo sin usar en 30 días se borra: su sesión murió hace mucho (24 h
# sin uso la cierran, y un refresco dura 7 días). Decidido el 5 nov 2026
DIAS_SIN_USO_PARA_BORRAR_UN_DISPOSITIVO = 30
# Un refresco caducado se borra a los 7 días: ya no sirve para nada
DIAS_TRAS_CADUCAR_PARA_BORRAR_UN_REFRESCO = 7


class PurgeStaleSessionsUseCase:
    """Borra los dispositivos sin uso desde hace 30 días y los refrescos caducados hace 7."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, request: PurgeStaleSessionsRequestDTO) -> PurgeStaleSessionsResponseDTO:
        """Una limpieza a la hora `request.ahora` (UTC, sin huso, como el resto de fechas)."""
        ahora = request.ahora
        async with self._uow:
            dispositivos = await self._uow.user_devices.delete_unused_since(
                ahora - timedelta(days=DIAS_SIN_USO_PARA_BORRAR_UN_DISPOSITIVO)
            )
            tokens = await self._uow.refresh_tokens.delete_expired_before(
                ahora - timedelta(days=DIAS_TRAS_CADUCAR_PARA_BORRAR_UN_REFRESCO)
            )
        return PurgeStaleSessionsResponseDTO(dispositivos=dispositivos, tokens=tokens)
