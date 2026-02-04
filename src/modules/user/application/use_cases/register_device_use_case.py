# src/modules/user/application/use_cases/register_device_use_case.py
"""
Register Device Use Case - Application Layer

Caso de uso para registrar o actualizar un dispositivo de usuario.

Responsabilidades:
- Detectar si el dispositivo es nuevo o conocido
- Crear dispositivo nuevo si no existe
- Actualizar last_used_at y ip_address si ya existe
- Lanzar evento NewDeviceDetectedEvent si es nuevo
- Retornar información del dispositivo + flag para setear cookie

Identificación de dispositivos (v2.0.4):
- PRIMARY: Cookie httpOnly device_id (no depende de IP)
- El fingerprint solo se usa para generar device_name legible

Llamado desde:
- LoginUserUseCase (en cada login exitoso)
- RefreshTokenUseCase (en cada refresh token exitoso)

Patrón: Use Case Pattern + Unit of Work
"""

import logging

from src.modules.user.application.dto.device_dto import (
    RegisterDeviceRequestDTO,
    RegisterDeviceResponseDTO,
)
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class RegisterDeviceUseCase:
    """
    Use Case para registrar/actualizar dispositivos de usuario.

    Flujo (v2.0.4 - Cookie-Based Identification):
    1. Si hay device_id_from_cookie:
       - Buscar por device_id + user_id (ownership validation)
       - Si existe y activo: update_last_used(), update_ip_address()
       - Retornar set_device_cookie=False (cookie ya existe)
    2. Si no hay cookie o device no encontrado:
       - Crear nuevo UserDevice con fingerprint
       - Lanzar evento NewDeviceDetectedEvent
       - Retornar set_device_cookie=True (caller debe setear cookie)

    Security (OWASP A01):
    - Ownership validation: device.user_id == jwt.user_id
    - Cookie httpOnly: JS no puede manipular device_id
    - IP solo para auditoría, no para identificación

    Examples:
        >>> # Login con cookie existente
        >>> request = RegisterDeviceRequestDTO(
        ...     user_id="550e8400-...",
        ...     user_agent="Mozilla/5.0...",
        ...     ip_address="192.168.1.100",
        ...     device_id_from_cookie="7c9e6679-..."
        ... )
        >>> response = await use_case.execute(request)
        >>> response.set_device_cookie
        False  # Cookie ya existe, no setear

        >>> # Login sin cookie (nuevo dispositivo)
        >>> request = RegisterDeviceRequestDTO(
        ...     user_id="550e8400-...",
        ...     user_agent="Mozilla/5.0...",
        ...     ip_address="192.168.1.100"
        ... )
        >>> response = await use_case.execute(request)
        >>> response.set_device_cookie
        True  # Caller debe setear cookie device_id
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work con acceso al user_devices repository
        """
        self._uow = uow

    async def execute(self, request: RegisterDeviceRequestDTO) -> RegisterDeviceResponseDTO:
        """
        Ejecuta el caso de uso de registro/actualización de dispositivo.

        Args:
            request: DTO con user_id, user_agent, ip_address, device_id_from_cookie

        Returns:
            RegisterDeviceResponseDTO con device_id, is_new_device, message, set_device_cookie

        Raises:
            ValueError: Si user_id no es UUID válido
            RepositoryError: Si falla la persistencia
        """
        async with self._uow:
            user_id = UserId(request.user_id)

            # =========================================================
            # PRIORITY 1: Cookie-based lookup (v2.0.4)
            # =========================================================
            if request.device_id_from_cookie:
                try:
                    device_id = UserDeviceId.from_string(request.device_id_from_cookie)
                    existing_device = await self._uow.user_devices.find_by_id_and_user(
                        device_id=device_id,
                        user_id=user_id,
                    )

                    if existing_device:
                        # Device found via cookie - update timestamps and IP
                        existing_device.update_last_used()
                        existing_device.update_ip_address(request.ip_address)
                        await self._uow.user_devices.save(existing_device)

                        logger.debug(
                            f"Device identified via cookie: {existing_device.device_name}"
                        )

                        return RegisterDeviceResponseDTO(
                            device_id=str(existing_device.id.value),
                            is_new_device=False,
                            message=f"Dispositivo actualizado: {existing_device.device_name}",
                            set_device_cookie=False,  # Cookie already valid
                        )

                except ValueError as e:
                    # Invalid device_id format in cookie - treat as no cookie
                    logger.warning(f"Invalid device_id in cookie: {e}")

            # =========================================================
            # PRIORITY 2: Fingerprint-based lookup (fallback)
            # =========================================================
            # Create fingerprint for device lookup and device_name generation
            fingerprint = DeviceFingerprint.create(
                user_agent=request.user_agent,
                ip_address=request.ip_address,
            )

            # Check if device already exists by fingerprint (prevents unique index violation)
            existing_device = await self._uow.user_devices.find_by_user_and_fingerprint(
                user_id=user_id,
                fingerprint_hash=fingerprint.fingerprint_hash,
            )

            if existing_device:
                # Device found via fingerprint - update timestamps and IP
                existing_device.update_last_used()
                existing_device.update_ip_address(request.ip_address)
                await self._uow.user_devices.save(existing_device)

                logger.debug(
                    f"Device identified via fingerprint (cookie missing): {existing_device.device_name}"
                )

                return RegisterDeviceResponseDTO(
                    device_id=str(existing_device.id.value),
                    is_new_device=False,
                    message=f"Dispositivo actualizado: {existing_device.device_name}",
                    set_device_cookie=True,  # Cookie was missing, caller must set it
                )

            # =========================================================
            # PRIORITY 3: Create new device
            # =========================================================
            new_device = UserDevice.create(
                user_id=user_id,
                fingerprint=fingerprint,
            )
            await self._uow.user_devices.save(new_device)

            logger.info(f"New device registered: {new_device.device_name}")

            return RegisterDeviceResponseDTO(
                device_id=str(new_device.id.value),
                is_new_device=True,
                message=f"Nuevo dispositivo detectado: {new_device.device_name}",
                set_device_cookie=True,  # Caller must set cookie
            )
