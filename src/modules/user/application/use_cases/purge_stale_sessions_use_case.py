"""
La limpieza de dispositivos y refrescos viejos (BE #737).

Hasta ahora no se borraba nada: en producción una cuenta tenía 193 dispositivos
(191 revocados) y 750 de 761 refrescos estaban caducados. Se guardaban para
siempre la IP y el navegador de cada uno, contra la minimización de datos (RGPD).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)

# Un dispositivo sin usar en 30 días se borra: su sesión murió hace mucho (24 h
# sin uso la cierran, y un refresco dura 7 días). Decidido el 5 nov 2026
DIAS_SIN_USO_PARA_BORRAR_UN_DISPOSITIVO = 30
# Un refresco caducado se borra a los 7 días: ya no sirve para nada
DIAS_TRAS_CADUCAR_PARA_BORRAR_UN_REFRESCO = 7


@dataclass(frozen=True)
class SesionesBorradas:
    """Cuántos dispositivos y refrescos se borraron en una vuelta."""

    dispositivos: int
    tokens: int


class PurgeStaleSessionsUseCase:
    """Borra los dispositivos sin uso desde hace 30 días y los refrescos caducados hace 7."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, ahora: datetime) -> SesionesBorradas:
        """Una limpieza a la hora `ahora` (UTC, sin huso, como el resto de fechas)."""
        async with self._uow:
            dispositivos = await self._uow.user_devices.delete_unused_since(
                ahora - timedelta(days=DIAS_SIN_USO_PARA_BORRAR_UN_DISPOSITIVO)
            )
            tokens = await self._uow.refresh_tokens.delete_expired_before(
                ahora - timedelta(days=DIAS_TRAS_CADUCAR_PARA_BORRAR_UN_REFRESCO)
            )
        return SesionesBorradas(dispositivos=dispositivos, tokens=tokens)
