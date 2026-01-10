# src/modules/user/infrastructure/api/v1/device_routes.py
"""
Device Routes - API Layer

Endpoints REST para gestión de dispositivos de usuario (Device Fingerprinting).

Endpoints:
- GET /api/v1/users/me/devices - Listar dispositivos activos
- DELETE /api/v1/users/me/devices/{device_id} - Revocar dispositivo

Security:
- Todos los endpoints requieren autenticación (JWT)
- Usuario solo puede ver/revocar sus propios dispositivos
- Rate limiting aplicado globalmente (100/min)

Patrón: REST API + Dependency Injection + DTOs
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.config.dependencies import (
    get_current_user,
    get_list_user_devices_use_case,
    get_revoke_device_use_case,
)
from src.modules.user.application.dto.device_dto import (
    ListUserDevicesRequestDTO,
    ListUserDevicesResponseDTO,
    RevokeDeviceRequestDTO,
    RevokeDeviceResponseDTO,
)
from src.modules.user.application.use_cases.list_user_devices_use_case import (
    ListUserDevicesUseCase,
)
from src.modules.user.application.use_cases.revoke_device_use_case import (
    RevokeDeviceUseCase,
)
from src.modules.user.domain.entities.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# ENDPOINTS - Device Management
# ============================================================================


@router.get(
    "/users/me/devices",
    response_model=ListUserDevicesResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Listar dispositivos activos",
    description="""
    Lista todos los dispositivos activos del usuario autenticado.

    **Características:**
    - Solo dispositivos con is_active=True
    - Ordenados por last_used_at DESC (más recientes primero)
    - Retorna lista vacía si no hay dispositivos

    **Security:**
    - Requiere autenticación JWT (httpOnly cookie)
    - Solo puede ver sus propios dispositivos

    **Use Case:**
    - Permite al usuario revisar qué dispositivos tienen acceso a su cuenta
    - Detectar sesiones sospechosas en dispositivos desconocidos
    - Gestionar dispositivos antes de revocar alguno

    **Example Response:**
    ```json
    {
      "devices": [
        {
          "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
          "device_name": "Chrome 120.0 on macOS",
          "ip_address": "192.168.1.100",
          "last_used_at": "2026-01-09T10:30:00Z",
          "created_at": "2026-01-08T14:20:00Z",
          "is_active": true
        },
        {
          "id": "8d0f7789-8536-51ef-b827-f18fd2g01bf8",
          "device_name": "Safari 17.0 on iOS",
          "ip_address": "192.168.1.101",
          "last_used_at": "2026-01-08T16:45:00Z",
          "created_at": "2026-01-07T12:10:00Z",
          "is_active": true
        }
      ],
      "total_count": 2
    }
    ```
    """,
    tags=["Devices"],
)
async def list_user_devices(
    current_user: User = Depends(get_current_user),
    use_case: ListUserDevicesUseCase = Depends(get_list_user_devices_use_case),
) -> ListUserDevicesResponseDTO:
    """
    Lista todos los dispositivos activos del usuario autenticado.

    Args:
        current_user: Usuario autenticado (extraído del JWT)
        use_case: Use case inyectado por DI

    Returns:
        ListUserDevicesResponseDTO con lista de dispositivos y contador

    Raises:
        HTTPException 401: Si no está autenticado
        HTTPException 500: Si falla la operación

    Examples:
        # Request
        GET /api/v1/users/me/devices
        Headers:
          Cookie: access_token=eyJhbGc...

        # Response 200
        {
          "devices": [...],
          "total_count": 3
        }

        # Response 200 (sin dispositivos)
        {
          "devices": [],
          "total_count": 0
        }
    """
    try:
        # Crear request DTO con user_id del JWT
        request = ListUserDevicesRequestDTO(user_id=str(current_user.id))

        # Ejecutar use case
        response = await use_case.execute(request)

        logger.info(
            f"User {current_user.id} listed {response.total_count} active devices"
        )

        return response

    except Exception as e:
        logger.error(f"Error listing devices for user {current_user.id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al listar dispositivos",
        ) from e


@router.delete(
    "/users/me/devices/{device_id}",
    response_model=RevokeDeviceResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Revocar dispositivo",
    description="""
    Revoca un dispositivo del usuario autenticado (marca como inactivo).

    **Características:**
    - Marca dispositivo como is_active=False (soft delete)
    - Lanza evento DeviceRevokedEvent para audit trail
    - NO elimina físicamente el registro
    - Dispositivo revocado NO aparece en listados

    **Security:**
    - Requiere autenticación JWT
    - Solo puede revocar sus propios dispositivos (validación interna)
    - HTTP 403 si intenta revocar dispositivo de otro usuario

    **Use Cases:**
    - Cerrar sesión de dispositivo perdido/robado
    - Revocar acceso de dispositivo compartido
    - Limpiar dispositivos antiguos que ya no usa

    **IMPORTANTE:**
    - NO cierra sesiones activas (solo marca dispositivo como revocado)
    - Para cerrar sesiones, usar logout endpoint

    **Example Response:**
    ```json
    {
      "message": "Dispositivo revocado exitosamente",
      "device_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
    }
    ```
    """,
    tags=["Devices"],
)
async def revoke_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    use_case: RevokeDeviceUseCase = Depends(get_revoke_device_use_case),
) -> RevokeDeviceResponseDTO:
    """
    Revoca un dispositivo del usuario autenticado.

    Args:
        device_id: UUID del dispositivo a revocar (path parameter)
        current_user: Usuario autenticado (extraído del JWT)
        use_case: Use case inyectado por DI

    Returns:
        RevokeDeviceResponseDTO con mensaje de confirmación

    Raises:
        HTTPException 400: Si device_id no es UUID válido
        HTTPException 403: Si el dispositivo no pertenece al usuario
        HTTPException 404: Si el dispositivo no existe
        HTTPException 409: Si el dispositivo ya estaba revocado
        HTTPException 500: Si falla la operación

    Examples:
        # Request
        DELETE /api/v1/users/me/devices/7c9e6679-7425-40de-944b-e07fc1f90ae7
        Headers:
          Cookie: access_token=eyJhbGc...

        # Response 200 (éxito)
        {
          "message": "Dispositivo revocado exitosamente",
          "device_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
        }

        # Response 404 (no existe)
        {
          "detail": "Dispositivo no encontrado"
        }

        # Response 403 (no autorizado)
        {
          "detail": "No autorizado para revocar este dispositivo"
        }

        # Response 409 (ya revocado)
        {
          "detail": "Dispositivo ya está revocado"
        }
    """
    try:
        # Crear request DTO con user_id y device_id
        request = RevokeDeviceRequestDTO(
            user_id=str(current_user.id),
            device_id=device_id,
        )

        # Ejecutar use case
        response = await use_case.execute(request)

        logger.info(f"User {current_user.id} revoked device {device_id}")

        return response

    except ValueError as e:
        # device_id inválido o dispositivo no existe
        logger.warning(f"Device not found: {device_id} - {e!s}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dispositivo {device_id} no encontrado",
        ) from e

    except PermissionError as e:
        # Dispositivo pertenece a otro usuario
        logger.warning(
            f"User {current_user.id} attempted to revoke device {device_id} (unauthorized)"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para revocar este dispositivo",
        ) from e

    except RuntimeError as e:
        # Dispositivo ya estaba revocado
        logger.warning(f"Device {device_id} already revoked - {e!s}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dispositivo ya está revocado",
        ) from e

    except Exception as e:
        logger.error(f"Error revoking device {device_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al revocar dispositivo",
        ) from e
