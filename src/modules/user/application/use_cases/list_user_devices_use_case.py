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

from src.modules.user.application.dto.device_dto import (
    ListUserDevicesRequestDTO,
    ListUserDevicesResponseDTO,
    UserDeviceDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


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

    async def execute(
        self, request: ListUserDevicesRequestDTO
    ) -> ListUserDevicesResponseDTO:
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

            # 3. Mapear entidades a DTOs
            device_dtos = [
                UserDeviceDTO(
                    id=str(device.id.value),
                    device_name=device.device_name,
                    ip_address=device.ip_address,
                    last_used_at=device.last_used_at,
                    created_at=device.created_at,
                    is_active=device.is_active,
                )
                for device in devices
            ]

            # 4. Retornar respuesta con lista + contador
            return ListUserDevicesResponseDTO(
                devices=device_dtos,
                total_count=len(device_dtos),
            )
