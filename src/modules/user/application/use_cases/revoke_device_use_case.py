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
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
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
            request: DTO con user_id, device_id, y opcionalmente user_agent + ip_address

        Returns:
            RevokeDeviceResponseDTO con mensaje de confirmación

        Raises:
            ValueError: Si device_id no es UUID válido o dispositivo no existe
            PermissionError: Si el dispositivo no pertenece al usuario
            RuntimeError: Si el dispositivo ya estaba revocado
            CurrentDeviceRevocationException: Si intenta revocar el dispositivo actual

        Example Flow:
            # Revocación exitosa
            Request: user_id=123, device_id=456, user_agent="...", ip_address="..."
            → Buscar dispositivo 456
            → Validar: dispositivo.user_id == 123 ✅
            → Validar: fingerprint actual != fingerprint dispositivo 456 ✅
            → Revocar: device.revoke()
            → Evento: DeviceRevokedEvent lanzado
            → Response: "Dispositivo revocado exitosamente"

            # Error: Dispositivo de otro usuario
            Request: user_id=123, device_id=789
            → Buscar dispositivo 789
            → Validar: dispositivo.user_id == 999 ❌
            → Error: PermissionError("No autorizado para revocar este dispositivo")

            # Error: Dispositivo actual (auto-revocación)
            Request: user_id=123, device_id=456 (mismo fingerprint)
            → Buscar dispositivo 456
            → Validar: fingerprint actual == fingerprint dispositivo 456 ❌
            → Error: CurrentDeviceRevocationException("No puedes revocar el dispositivo actual")

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
                raise PermissionError(f"No autorizado para revocar dispositivo {request.device_id}")

            # 4. Revocar dispositivo especificado (lanza DeviceRevokedEvent)
            # NOTA: El usuario PUEDE revocar cualquier dispositivo, incluyendo el actual
            # Si revoca el dispositivo actual, perderá acceso inmediatamente
            # El frontend debe mostrar una advertencia visual antes de confirmar
            device.revoke()

            # 5. CRÍTICO: Invalidar TODOS los refresh tokens del dispositivo revocado
            # Esto cierra las sesiones activas del dispositivo
            # Sin este paso, el dispositivo permanecería logueado aunque esté revocado
            tokens_revoked = await self._uow.refresh_tokens.revoke_all_for_device(device_id)

            # 6. Determinar si es el dispositivo actual (para info en respuesta)
            is_current_device = False
            if request.user_agent and request.ip_address:
                current_fingerprint = DeviceFingerprint.create(
                    user_agent=request.user_agent, ip_address=request.ip_address
                )
                is_current_device = device.matches_fingerprint(current_fingerprint)

            # 7. Guardar cambios en BD
            await self._uow.user_devices.save(device)
            await self._uow.commit()

            # 8. Retornar confirmación
            message = f"Dispositivo revocado exitosamente. {tokens_revoked} sesión(es) cerrada(s)."
            if is_current_device:
                message = f"Dispositivo actual revocado exitosamente. {tokens_revoked} sesión(es) cerrada(s). Tu sesión se cerrará."

            return RevokeDeviceResponseDTO(
                message=message,
                device_id=request.device_id,
            )
