# src/modules/user/application/use_cases/register_device_use_case.py
"""
Register Device Use Case - Application Layer

Caso de uso para registrar o actualizar un dispositivo de usuario.

Responsabilidades:
- Detectar si el dispositivo es nuevo o conocido (por fingerprint)
- Crear dispositivo nuevo si no existe
- Actualizar last_used_at si ya existe
- Lanzar evento NewDeviceDetectedEvent si es nuevo
- Retornar información del dispositivo

Llamado desde:
- LoginUserUseCase (en cada login exitoso)
- RefreshTokenUseCase (en cada refresh token exitoso)

Patrón: Use Case Pattern + Unit of Work
"""

from src.modules.user.application.dto.device_dto import (
    RegisterDeviceRequestDTO,
    RegisterDeviceResponseDTO,
)
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_id import UserId


class RegisterDeviceUseCase:
    """
    Use Case para registrar/actualizar dispositivos de usuario.

    Flujo:
    1. Crear DeviceFingerprint (genera hash SHA256 automáticamente)
    2. Buscar dispositivo existente por user_id + fingerprint_hash
    3. Si NO existe:
       - Crear nuevo UserDevice
       - Lanzar evento NewDeviceDetectedEvent
       - Retornar is_new_device=True
    4. Si SÍ existe:
       - Actualizar last_used_at
       - Retornar is_new_device=False
    5. Guardar en BD mediante UoW

    Security:
    - El hash SHA256 del fingerprint previene duplicados
    - DeviceFingerprint combina: device_name + user_agent + IP
    - Índice único parcial en BD (user_id + fingerprint_hash + is_active)

    Examples:
        >>> # Login exitoso - registrar dispositivo
        >>> request = RegisterDeviceRequestDTO(
        ...     user_id="550e8400-...",
        ...     device_name="Chrome 120.0 on macOS",
        ...     user_agent="Mozilla/5.0...",
        ...     ip_address="192.168.1.100"
        ... )
        >>> response = await use_case.execute(request)
        >>> if response.is_new_device:
        ...     print(f"Nuevo dispositivo detectado: {response.device_id}")
        ...     # Enviar email al usuario notificando dispositivo nuevo
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work con acceso al user_devices repository
        """
        self._uow = uow

    async def execute(
        self, request: RegisterDeviceRequestDTO
    ) -> RegisterDeviceResponseDTO:
        """
        Ejecuta el caso de uso de registro/actualización de dispositivo.

        Args:
            request: DTO con user_id, device_name, user_agent, ip_address

        Returns:
            RegisterDeviceResponseDTO con device_id, is_new_device, message

        Raises:
            ValueError: Si user_id no es UUID válido
            RepositoryError: Si falla la persistencia

        Example Flow:
            # Dispositivo nuevo (primera vez)
            Request: user_id=123, user_agent="Chrome/120.0", ip="192.168.1.1"
            → DeviceFingerprint genera hash: "a1b2c3d4..."
            → Búsqueda: NO existe en BD
            → Crear UserDevice.create()
            → Evento: NewDeviceDetectedEvent lanzado
            → Response: is_new_device=True

            # Dispositivo conocido (segunda vez con mismo fingerprint)
            Request: user_id=123, user_agent="Chrome/120.0", ip="192.168.1.1"
            → DeviceFingerprint genera hash: "a1b2c3d4..." (mismo)
            → Búsqueda: SÍ existe en BD
            → Actualizar: device.update_last_used()
            → Response: is_new_device=False
        """
        async with self._uow:
            # 1. Parsear user_id de string a UserId
            user_id = UserId(request.user_id)

            # 2. Crear DeviceFingerprint (genera hash SHA256 y device_name automáticamente)
            fingerprint = DeviceFingerprint.create(
                user_agent=request.user_agent,
                ip_address=request.ip_address,
            )

            # 3. Buscar dispositivo existente por user_id + fingerprint
            existing_device = await self._uow.user_devices.find_by_user_and_fingerprint(
                user_id=user_id,
                fingerprint=fingerprint,
            )

            # 4. Dispositivo conocido → Actualizar last_used_at
            if existing_device:
                existing_device.update_last_used()
                await self._uow.user_devices.save(existing_device)
                await self._uow.commit()

                return RegisterDeviceResponseDTO(
                    device_id=str(existing_device.id.value),
                    is_new_device=False,
                    message=f"Dispositivo conocido actualizado: {existing_device.device_name}",
                )

            # 5. Dispositivo nuevo → Crear + Lanzar evento
            new_device = UserDevice.create(
                user_id=user_id,
                fingerprint=fingerprint,
            )
            await self._uow.user_devices.save(new_device)
            await self._uow.commit()

            return RegisterDeviceResponseDTO(
                device_id=str(new_device.id.value),
                is_new_device=True,
                message=f"Nuevo dispositivo detectado: {new_device.device_name}",
            )
