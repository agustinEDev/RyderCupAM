# src/modules/user/application/dto/device_dto.py
"""
Device DTOs - Application Layer

DTOs (Data Transfer Objects) para Device Fingerprinting.
Validan datos de entrada/salida de los Use Cases.

Patrón: DTO Pattern + Pydantic Validation
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ======================================================================================
# DTO para el Caso de Uso: Register/Update Device
# ======================================================================================


class RegisterDeviceRequestDTO(BaseModel):
    """
    DTO de entrada para registrar/actualizar un dispositivo.

    Este DTO NO se usa directamente en endpoints (los datos vienen del request HTTP).
    Se construye internamente en LoginUseCase y RefreshTokenUseCase.

    Fields:
        user_id: ID del usuario propietario (extraído del JWT)
        user_agent: User-Agent completo del navegador
        ip_address: IP del cliente (IPv4 o IPv6)

    Note:
        device_name NO es necesario - DeviceFingerprint.create() lo genera automáticamente
        parseando el user_agent (ej: "Chrome 120.0 on macOS")
    """

    user_id: str = Field(
        ...,
        description="ID del usuario propietario del dispositivo",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    user_agent: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="User-Agent completo del navegador",
        json_schema_extra={
            "example": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        },
    )
    ip_address: str = Field(
        ...,
        min_length=7,
        max_length=45,
        description="Dirección IP del cliente (IPv4 o IPv6)",
        json_schema_extra={"example": "192.168.1.100"},
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "ip_address": "192.168.1.100",
            }
        },
    )


class RegisterDeviceResponseDTO(BaseModel):
    """
    DTO de salida para RegisterDeviceUseCase.

    Retorna información del dispositivo registrado/actualizado.

    Fields:
        device_id: ID único del dispositivo
        is_new_device: True si es dispositivo nuevo, False si ya existía
        message: Mensaje descriptivo
    """

    device_id: str = Field(
        ...,
        description="ID único del dispositivo",
        json_schema_extra={"example": "7c9e6679-7425-40de-944b-e07fc1f90ae7"},
    )
    is_new_device: bool = Field(
        ...,
        description="True si es un dispositivo nuevo, False si ya existía",
        json_schema_extra={"example": True},
    )
    message: str = Field(
        ...,
        description="Mensaje descriptivo de la operación",
        json_schema_extra={"example": "Nuevo dispositivo detectado: Chrome on macOS"},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                "is_new_device": True,
                "message": "Nuevo dispositivo detectado: Chrome on macOS",
            }
        }
    )


# ======================================================================================
# DTO para el Caso de Uso: List User Devices
# ======================================================================================


class UserDeviceDTO(BaseModel):
    """
    DTO para representar un dispositivo de usuario.

    Usado en listas y respuestas individuales.

    Fields:
        id: ID del dispositivo
        device_name: Nombre del dispositivo
        ip_address: Última IP registrada
        last_used_at: Última vez que se usó el dispositivo
        created_at: Fecha de creación del dispositivo
        is_active: Estado del dispositivo (activo/revocado)
    """

    id: str = Field(
        ...,
        description="ID único del dispositivo",
        json_schema_extra={"example": "7c9e6679-7425-40de-944b-e07fc1f90ae7"},
    )
    device_name: str = Field(
        ...,
        description="Nombre del dispositivo",
        json_schema_extra={"example": "Chrome 120.0 on macOS"},
    )
    ip_address: str = Field(
        ...,
        description="Última dirección IP registrada",
        json_schema_extra={"example": "192.168.1.100"},
    )
    last_used_at: datetime = Field(
        ...,
        description="Última vez que se usó el dispositivo",
        json_schema_extra={"example": "2026-01-09T10:30:00Z"},
    )
    created_at: datetime = Field(
        ...,
        description="Fecha de creación del dispositivo",
        json_schema_extra={"example": "2026-01-08T14:20:00Z"},
    )
    is_active: bool = Field(
        ...,
        description="Estado del dispositivo (True=activo, False=revocado)",
        json_schema_extra={"example": True},
    )

    model_config = ConfigDict(
        from_attributes=True,  # Permite crear desde entidades ORM
        json_schema_extra={
            "example": {
                "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                "device_name": "Chrome 120.0 on macOS",
                "ip_address": "192.168.1.100",
                "last_used_at": "2026-01-09T10:30:00Z",
                "created_at": "2026-01-08T14:20:00Z",
                "is_active": True,
            }
        },
    )


class ListUserDevicesRequestDTO(BaseModel):
    """
    DTO de entrada para listar dispositivos de un usuario.

    Fields:
        user_id: ID del usuario (extraído del JWT)
    """

    user_id: str = Field(
        ...,
        description="ID del usuario propietario de los dispositivos",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class ListUserDevicesResponseDTO(BaseModel):
    """
    DTO de salida para ListUserDevicesUseCase.

    Retorna lista de dispositivos activos del usuario.

    Fields:
        devices: Lista de dispositivos activos
        total_count: Cantidad total de dispositivos
    """

    devices: list[UserDeviceDTO] = Field(
        ...,
        description="Lista de dispositivos activos del usuario",
    )
    total_count: int = Field(
        ...,
        description="Cantidad total de dispositivos activos",
        json_schema_extra={"example": 3},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "devices": [
                    {
                        "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                        "device_name": "Chrome 120.0 on macOS",
                        "ip_address": "192.168.1.100",
                        "last_used_at": "2026-01-09T10:30:00Z",
                        "created_at": "2026-01-08T14:20:00Z",
                        "is_active": True,
                    },
                    {
                        "id": "8d0f7789-8536-51ef-b827-f18fd2g01bf8",
                        "device_name": "Safari 17.0 on iOS",
                        "ip_address": "192.168.1.101",
                        "last_used_at": "2026-01-08T16:45:00Z",
                        "created_at": "2026-01-07T12:10:00Z",
                        "is_active": True,
                    },
                ],
                "total_count": 2,
            }
        }
    )


# ======================================================================================
# DTO para el Caso de Uso: Revoke Device
# ======================================================================================


class RevokeDeviceRequestDTO(BaseModel):
    """
    DTO de entrada para revocar un dispositivo.

    Fields:
        user_id: ID del usuario propietario (validación de autorización)
        device_id: ID del dispositivo a revocar
        user_agent: User-Agent del request actual (opcional, para validar dispositivo actual)
        ip_address: IP del request actual (opcional, para validar dispositivo actual)

    Note:
        Los campos user_agent e ip_address son opcionales para mantener compatibilidad
        con tests existentes, pero se DEBEN proporcionar en endpoints reales para
        prevenir auto-revocación del dispositivo actual.
    """

    user_id: str = Field(
        ...,
        description="ID del usuario propietario del dispositivo",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    device_id: str = Field(
        ...,
        description="ID del dispositivo a revocar",
        json_schema_extra={"example": "7c9e6679-7425-40de-944b-e07fc1f90ae7"},
    )
    user_agent: str | None = Field(
        default=None,
        min_length=10,
        max_length=2000,
        description="User-Agent del request actual (para prevenir auto-revocación)",
        json_schema_extra={
            "example": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        },
    )
    ip_address: str | None = Field(
        default=None,
        min_length=7,
        max_length=45,
        description="IP del request actual (para prevenir auto-revocación)",
        json_schema_extra={"example": "192.168.1.100"},
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class RevokeDeviceResponseDTO(BaseModel):
    """
    DTO de salida para RevokeDeviceUseCase.

    Confirma que el dispositivo fue revocado exitosamente.

    Fields:
        message: Mensaje de confirmación
        device_id: ID del dispositivo revocado
    """

    message: str = Field(
        ...,
        description="Mensaje de confirmación",
        json_schema_extra={"example": "Dispositivo revocado exitosamente"},
    )
    device_id: str = Field(
        ...,
        description="ID del dispositivo revocado",
        json_schema_extra={"example": "7c9e6679-7425-40de-944b-e07fc1f90ae7"},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Dispositivo revocado exitosamente",
                "device_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            }
        }
    )
