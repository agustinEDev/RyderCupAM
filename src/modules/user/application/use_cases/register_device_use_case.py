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
from src.modules.user.domain.services.cookie_de_dispositivo import ids_de_la_cookie_de_dispositivo
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
       - recognized_by_cookie=True
    2. Si no hay cookie o device no encontrado:
       - Buscarlo por la huella, o crear uno nuevo
       - Lanzar evento NewDeviceDetectedEvent
    La ruta pone la cookie del dispositivo siempre (BE #737)

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
        >>> response.recognized_by_cookie
        True

        >>> # Login sin cookie (nuevo dispositivo)
        >>> request = RegisterDeviceRequestDTO(
        ...     user_id="550e8400-...",
        ...     user_agent="Mozilla/5.0...",
        ...     ip_address="192.168.1.100"
        ... )
        >>> response = await use_case.execute(request)
        >>> response.is_new_device
        True
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
            RegisterDeviceResponseDTO con device_id, is_new_device, message, recognized_by_cookie

        Raises:
            ValueError: Si user_id no es UUID válido
            RepositoryError: Si falla la persistencia
        """
        async with self._uow:
            user_id = UserId(request.user_id)

            # =========================================================
            # PRIORITY 1: Cookie-based lookup (v2.0.4)
            # =========================================================
            # La cookie guarda los dispositivos de hasta 5 cuentas del navegador (BE
            # #737): vale el primero que sea de este usuario y siga activo
            for id_de_la_cookie in ids_de_la_cookie_de_dispositivo(request.device_id_from_cookie):
                device_id = UserDeviceId.from_string(id_de_la_cookie)
                existing_device = await self._uow.user_devices.find_by_id_and_user(
                    device_id=device_id,
                    user_id=user_id,
                )
                if existing_device:
                    logger.debug(f"Device identified via cookie: {existing_device.device_name}")
                    # El navegador se actualizó, o es otro en este dispositivo
                    existing_device.update_user_agent(request.user_agent)
                    existing_device.update_country(request.country_code)
                    existing_device.update_installed_app(request.installed_app)
                    return await self._reusa(
                        existing_device, request.ip_address, por_su_cookie=True
                    )

            # =========================================================
            # PRIORITY 2: Fingerprint-based lookup (fallback)
            # =========================================================
            # Create fingerprint for device lookup and device_name generation
            fingerprint = DeviceFingerprint.create(
                user_agent=request.user_agent,
                ip_address=request.ip_address,
                installed_app=request.installed_app,
            )

            # Check if device already exists by fingerprint (prevents unique index violation)
            existing_device = await self._uow.user_devices.find_by_user_and_fingerprint(
                user_id=user_id,
                fingerprint_hash=fingerprint.fingerprint_hash,
            )

            if existing_device:
                logger.debug(
                    f"Device identified via fingerprint (cookie missing): {existing_device.device_name}"
                )
                return await self._reusa(
                    existing_device, request.ip_address, country_code=request.country_code
                )

            # =========================================================
            # PRIORITY 3: Create new device
            # =========================================================
            new_device = UserDevice.create(
                user_id=user_id,
                fingerprint=fingerprint,
                installed_app=request.installed_app,
                country_code=request.country_code,
            )
            # Si otro inicio de sesión a la vez lo dio de alta, el suyo (BE #692)
            guardado = await self._uow.user_devices.add_unless_registered(new_device)
            if guardado is not new_device:
                return await self._reusa(
                    guardado, request.ip_address, country_code=request.country_code
                )

            logger.info(f"New device registered: {new_device.device_name}")

            return RegisterDeviceResponseDTO(
                device_id=str(new_device.id.value),
                is_new_device=True,
                message=f"Nuevo dispositivo detectado: {new_device.device_name}",
            )

    async def _reusa(
        self,
        device: UserDevice,
        ip_address: str,
        country_code: str | None = None,
        por_su_cookie: bool = False,
    ) -> RegisterDeviceResponseDTO:
        """El que ya estaba, al día."""
        await self._reanuda(device)
        device.update_ip_address(ip_address)
        device.update_country(country_code)
        await self._uow.user_devices.save(device)
        return RegisterDeviceResponseDTO(
            device_id=str(device.id.value),
            is_new_device=False,
            message=f"Dispositivo actualizado: {device.device_name}",
            recognized_by_cookie=por_su_cookie,
        )

    async def _reanuda(self, device: UserDevice) -> None:
        """Vuelve a usar un dispositivo: su último uso pasa a ahora.

        Si estaba inactivo (BE #376), antes se revocan sus tokens anteriores. La
        caducidad por inactividad solo revoca un token cuando alguien intenta
        refrescar con él; sin esto, poner «último uso: ahora» haría valer otra
        vez los que nadie llegó a usar, uno robado incluido (CWE-613).
        """
        if device.is_idle():
            await self._uow.refresh_tokens.revoke_all_for_device(device.id)
        device.update_last_used()
