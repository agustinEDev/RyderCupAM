"""
Implementación en memoria del repositorio de dispositivos de usuario.

Este módulo implementa UserDeviceRepositoryInterface para tests unitarios.
Los datos se almacenan en diccionarios Python en memoria.
"""


from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.repositories.user_device_repository_interface import (
    UserDeviceRepositoryInterface,
)
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryUserDeviceRepository(UserDeviceRepositoryInterface):
    """
    Implementación en memoria del repositorio de dispositivos.

    Almacena dispositivos en diccionarios Python para tests unitarios.
    NO usar en producción (sin persistencia real).
    """

    def __init__(self):
        """Inicializa el repositorio en memoria vacío."""
        self._devices: dict[str, UserDevice] = {}

    async def save(self, device: UserDevice) -> None:
        """
        Guarda dispositivo en memoria.

        Args:
            device: UserDevice a guardar

        Note:
            Si el ID ya existe, sobrescribe (upsert behavior).
        """
        device_key = str(device.id.value)
        self._devices[device_key] = device

    async def find_by_id(self, device_id: UserDeviceId) -> UserDevice | None:
        """
        Busca dispositivo por ID.

        Args:
            device_id: ID del dispositivo

        Returns:
            Optional[UserDevice]: Dispositivo si existe, None si no

        """
        device_key = str(device_id.value)
        return self._devices.get(device_key)

    async def find_by_user_and_fingerprint(
        self, user_id: UserId, fingerprint: DeviceFingerprint
    ) -> UserDevice | None:
        """
        Busca dispositivo activo por usuario y fingerprint.

        Args:
            user_id: ID del usuario
            fingerprint: Fingerprint del dispositivo

        Returns:
            Optional[UserDevice]: Dispositivo activo si existe, None si no

        Note:
            Solo retorna dispositivos activos (is_active=TRUE).
        """
        for device in self._devices.values():
            if (
                device.user_id == user_id
                and device.fingerprint_hash == fingerprint.fingerprint_hash
                and device.is_active
            ):
                return device
        return None

    async def find_active_by_user(self, user_id: UserId) -> list[UserDevice]:
        """
        Lista todos los dispositivos activos de un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            List[UserDevice]: Lista de dispositivos activos

        Note:
            Solo retorna dispositivos activos (is_active=TRUE).
        """
        active_devices = [
            device
            for device in self._devices.values()
            if device.user_id == user_id and device.is_active
        ]
        return active_devices

    async def revoke(self, device_id: UserDeviceId) -> None:
        """
        Revoca un dispositivo (soft delete).

        Args:
            device_id: ID del dispositivo a revocar

        Raises:
            ValueError: Si el dispositivo no existe

        Note:
            Marca is_active=FALSE en lugar de eliminar.
        """
        device = await self.find_by_id(device_id)
        if not device:
            raise ValueError(f"Dispositivo {device_id} no encontrado")

        device.revoke()
        await self.save(device)  # Update in memory
