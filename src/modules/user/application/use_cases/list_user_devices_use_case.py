# src/modules/user/application/use_cases/list_user_devices_use_case.py
"""
List User Devices Use Case - Application Layer

Caso de uso para listar los dispositivos activos de un usuario.

Responsabilidades:
- Buscar todos los dispositivos activos del usuario
- Mapear entidades a DTOs
- Ordenar por last_used_at desc (más recientes primero)
- Retornar lista + contador

Llamado desde:
- GET /api/v1/users/me/devices (endpoint protegido)

Patrón: Use Case Pattern + Unit of Work + DTO Mapper
"""

import logging

from src.modules.user.application.dto.device_dto import (
    ListUserDevicesRequestDTO,
    ListUserDevicesResponseDTO,
    UserDeviceDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.http.http_context_validator import (
    validate_ip_address,
    validate_user_agent,
)

logger = logging.getLogger(__name__)


class ListUserDevicesUseCase:
    """
    Use Case para listar dispositivos activos de un usuario.

    Características:
    - Solo lista dispositivos con is_active=True
    - Ordenados por last_used_at DESC (más recientes primero)
    - Incluye total_count para paginación futura
    - Retorna lista vacía si el usuario no tiene dispositivos

    Security:
    - Solo puede listar sus propios dispositivos (user_id del JWT)
    - Dispositivos revocados NO se muestran

    Examples:
        >>> request = ListUserDevicesRequestDTO(user_id="550e8400-...")
        >>> response = await use_case.execute(request)
        >>> print(f"Total de dispositivos: {response.total_count}")
        >>> for device in response.devices:
        ...     print(f"{device.device_name} - Usado: {device.last_used_at}")
        Chrome on macOS - Usado: 2026-01-09 10:30:00
        Safari on iOS - Usado: 2026-01-08 14:20:00
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        """
        Inicializa el caso de uso.

        Args:
            uow: Unit of Work con acceso al user_devices repository
        """
        self._uow = uow

    async def execute(self, request: ListUserDevicesRequestDTO) -> ListUserDevicesResponseDTO:
        """
        Ejecuta el caso de uso de listado de dispositivos.

        Args:
            request: DTO con user_id (extraído del JWT)

        Returns:
            ListUserDevicesResponseDTO con lista de dispositivos y contador

        Raises:
            ValueError: Si user_id no es UUID válido

        Example:
            # Usuario con 2 dispositivos
            Response: {
                "devices": [
                    {
                        "id": "7c9e6679-...",
                        "device_name": "Chrome 120.0 on macOS",
                        "ip_address": "192.168.1.100",
                        "last_used_at": "2026-01-09T10:30:00Z",
                        "created_at": "2026-01-08T14:20:00Z",
                        "is_active": true
                    },
                    ...
                ],
                "total_count": 2
            }

            # Usuario sin dispositivos
            Response: {
                "devices": [],
                "total_count": 0
            }
        """
        async with self._uow:
            # 1. Parsear user_id de string a UserId
            user_id = UserId(request.user_id)

            # 2. Buscar todos los dispositivos activos del usuario
            devices = await self._uow.user_devices.find_active_by_user(user_id)

            # 3. Crear fingerprint del dispositivo actual (si hay contexto HTTP válido)
            # v1.13.1: Detectar dispositivo actual para marcar is_current_device
            # Validaciones aplicadas:
            # - Rechazar valores sentinel (unknown, "", whitespace, 0.0.0.0)
            # - Validar formato de IP y User-Agent
            # - Graceful degradation: si falla, current_fingerprint = None
            current_fingerprint = None

            # Validar user_agent e ip_address ANTES de crear fingerprint
            validated_user_agent = validate_user_agent(request.user_agent)
            validated_ip_address = validate_ip_address(request.ip_address)

            if validated_user_agent and validated_ip_address:
                try:
                    current_fingerprint = DeviceFingerprint.create(
                        user_agent=validated_user_agent,
                        ip_address=validated_ip_address,
                    )
                    logger.debug(
                        f"Current device fingerprint created: {current_fingerprint.device_name}"
                    )
                except (ValueError, Exception) as e:
                    # Graceful degradation: NO fallar el endpoint si no se puede crear fingerprint
                    # El usuario podrá ver sus dispositivos, solo no se marcará is_current_device
                    logger.warning(
                        f"Failed to create device fingerprint for current device: {e}. "
                        f"UA='{request.user_agent}', IP='{request.ip_address}'"
                    )
                    current_fingerprint = None
            else:
                # Valores no válidos (sentinel o malformados)
                logger.debug(
                    f"Skipping fingerprint creation due to invalid values. "
                    f"UA valid={validated_user_agent is not None}, "
                    f"IP valid={validated_ip_address is not None}"
                )

            # 4. Mapear entidades a DTOs (con is_current_device calculado)
            device_dtos = [
                UserDeviceDTO(
                    id=str(device.id.value),
                    device_name=device.device_name,
                    ip_address=device.ip_address,
                    last_used_at=device.last_used_at,
                    created_at=device.created_at,
                    is_active=device.is_active,
                    is_current_device=(
                        device.matches_fingerprint(current_fingerprint)
                        if current_fingerprint
                        else False
                    ),
                )
                for device in devices
            ]

            # 5. Retornar respuesta con lista + contador
            return ListUserDevicesResponseDTO(
                devices=device_dtos,
                total_count=len(device_dtos),
            )
