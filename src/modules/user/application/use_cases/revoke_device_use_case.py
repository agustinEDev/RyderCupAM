# src/modules/user/application/use_cases/revoke_device_use_case.py
"""
Revoke Device Use Case - Application Layer

Caso de uso para revocar un dispositivo de usuario (marca como inactivo).

Responsabilidades:
- Validar que el dispositivo pertenece al usuario (autorización)
- Marcar dispositivo como inactivo (is_active=False)
- Lanzar evento DeviceRevokedEvent
- Retornar confirmación

Llamado desde:
- DELETE /api/v1/users/me/devices/{device_id} (endpoint protegido)

Patrón: Use Case Pattern + Unit of Work + Domain Events
"""

from src.modules.user.application.dto.device_dto import (
    RevokeDeviceRequestDTO,
    RevokeDeviceResponseDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


class RevokeDeviceUseCase:
    """
    Use Case para revocar dispositivos de usuario.

    Características:
    - Valida propiedad del dispositivo (seguridad)
    - Marca dispositivo como inactivo (is_active=False)
    - Lanza evento DeviceRevokedEvent para audit trail
    - No elimina físicamente (soft delete)

    Security:
    - Solo puede revocar sus propios dispositivos (validación user_id)
    - Dispositivos revocados NO se muestran en listados
    - Índice único parcial permite reactivar fingerprint (futuro)

    Examples:
        >>> request = RevokeDeviceRequestDTO(
        ...     user_id="550e8400-...",
        ...     device_id="7c9e6679-..."
        ... )
        >>> response = await use_case.execute(request)
        >>> print(response.message)
        Dispositivo revocado exitosamente
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work con acceso al user_devices repository
        """
        self._uow = uow

    async def execute(self, request: RevokeDeviceRequestDTO) -> RevokeDeviceResponseDTO:
        """
        Ejecuta el caso de uso de revocación de dispositivo.

        Args:
            request: DTO con user_id y device_id

        Returns:
            RevokeDeviceResponseDTO con mensaje de confirmación

        Raises:
            ValueError: Si device_id no es UUID válido o dispositivo no existe
            PermissionError: Si el dispositivo no pertenece al usuario
            RuntimeError: Si el dispositivo ya estaba revocado

        Example Flow:
            # Revocación exitosa
            Request: user_id=123, device_id=456
            → Buscar dispositivo 456
            → Validar: dispositivo.user_id == 123 ✅
            → Revocar: device.revoke()
            → Evento: DeviceRevokedEvent lanzado
            → Response: "Dispositivo revocado exitosamente"

            # Error: Dispositivo de otro usuario
            Request: user_id=123, device_id=789
            → Buscar dispositivo 789
            → Validar: dispositivo.user_id == 999 ❌
            → Error: PermissionError("No autorizado para revocar este dispositivo")

            # Error: Dispositivo ya revocado
            Request: user_id=123, device_id=456 (ya revocado)
            → device.revoke() → RuntimeError("Device already revoked")
        """
        async with self._uow:
            # 1. Parsear IDs de string a Value Objects
            user_id = UserId(request.user_id)
            device_id = UserDeviceId.from_string(request.device_id)

            # 2. Buscar dispositivo por ID
            device = await self._uow.user_devices.find_by_id(device_id)
            if not device:
                raise ValueError(f"Dispositivo {request.device_id} no encontrado")

            # 3. Validar que el dispositivo pertenece al usuario (autorización)
            if device.user_id != user_id:
                raise PermissionError(
                    f"No autorizado para revocar dispositivo {request.device_id}"
                )

            # 4. Revocar dispositivo (lanza DeviceRevokedEvent)
            device.revoke()

            # 5. Guardar cambios en BD
            await self._uow.user_devices.save(device)
            await self._uow.commit()

            # 6. Retornar confirmación
            return RevokeDeviceResponseDTO(
                message="Dispositivo revocado exitosamente",
                device_id=request.device_id,
            )
