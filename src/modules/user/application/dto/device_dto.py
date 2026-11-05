# src/modules/user/application/dto/device_dto.py
"""
Device DTOs - Application Layer

DTOs (Data Transfer Objects) para Device Fingerprinting.
Validan datos de entrada/salida de los Use Cases.

Patrón: DTO Pattern + Pydantic Validation
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# Placeholder usado cuando get_trusted_client_ip() no puede resolver una IP real
# (p.ej. tráfico vía kubectl port-forward, donde el peer siempre es 127.0.0.1 y
# validate_ip_address() lo rechaza como sentinel). Sin esto, el registro de
# dispositivo se saltaba por completo y la cookie device_id nunca se fijaba,
# dejando al usuario sin ningún dispositivo "current" — lo que
# useDeviceRevocationMonitor del frontend interpreta como revocación y fuerza
# logout inmediato. DeviceFingerprint.create() exige una IP sintácticamente
# válida, de ahí "0.0.0.0" (ya reconocida como sentinel en el resto del código)
# en vez de un string arbitrario como "unknown".
# Sin User-Agent (o uno demasiado corto) también hay dispositivo (BE #737, auditoría
# OWASP A07): sin él la sesión no salía en la lista, no avisaba y no se podía revocar
UNKNOWN_USER_AGENT = "unknown-user-agent"
LONGITUD_MINIMA_DEL_USER_AGENT = 10


def agente_para_el_registro(user_agent: str | None) -> str:
    """El User-Agent con el que registrar el dispositivo: el que llegó, o el desconocido."""
    if user_agent and len(user_agent) >= LONGITUD_MINIMA_DEL_USER_AGENT:
        return user_agent
    return UNKNOWN_USER_AGENT


UNRESOLVED_IP_PLACEHOLDER = "0.0.0.0"  # nosec B104 - valor de relleno para una IP sin resolver, no una escucha en todas las interfaces

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
        device_id_from_cookie: ID del dispositivo desde cookie httpOnly (v2.0.4)

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
        min_length=LONGITUD_MINIMA_DEL_USER_AGENT,
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
    device_id_from_cookie: str | None = Field(
        default=None,
        min_length=36,
        max_length=36 * 5 + 4,  # hasta 5 ids separados por puntos (BE #737)
        description="ID del dispositivo desde cookie httpOnly (v2.0.4). Primary identifier.",
        json_schema_extra={"example": "7c9e6679-7425-40de-944b-e07fc1f90ae7"},
    )
    installed_app: bool = Field(
        default=False,
        description="La app instalada (PWA), por la cabecera X-App-Mode: standalone (BE #737)",
    )
    country_code: str | None = Field(
        default=None,
        max_length=2,
        description="País (ISO 3166 alfa-2) que da Cloudflare, solo con su secreto (BE #737)",
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "ip_address": "192.168.1.100",
                "device_id_from_cookie": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
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
        set_device_cookie: True si el caller debe setear la cookie device_id (v2.0.4)
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
    set_device_cookie: bool = Field(
        default=False,
        description="True si el caller debe setear la cookie device_id (v2.0.4)",
        json_schema_extra={"example": True},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                "is_new_device": True,
                "message": "Nuevo dispositivo detectado: Chrome on macOS",
                "set_device_cookie": True,
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
        is_current_device: True si es el dispositivo desde el cual se hace el request (v1.13.1)
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
    user_agent: str | None = Field(
        default=None,
        description="User-Agent del navegador del dispositivo (BE #737)",
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
    device_type: str = Field(
        default="unknown",
        description="Tipo para el icono: phone, tablet, computer o unknown (BE #737)",
    )
    platform: str = Field(
        default="unknown",
        description="iphone, ipad, mac, android, windows, chromebook, linux o unknown (BE #737)",
    )
    browser: str = Field(
        default="unknown",
        description="safari, chrome, firefox, edge, opera, samsung, instagram, google, "
        "facebook o unknown (BE #737)",
    )
    installed_app: bool = Field(
        default=False,
        description="Si es la app instalada (PWA) y no el navegador (BE #737)",
    )
    country_code: str | None = Field(
        default=None,
        description="País aproximado de la última conexión, ISO 3166 alfa-2 (BE #737)",
    )
    is_active: bool = Field(
        ...,
        description="Estado del dispositivo (True=activo, False=revocado)",
        json_schema_extra={"example": True},
    )
    is_current_device: bool = Field(
        ...,
        description="True si es el dispositivo actual desde el que se realiza el request (v1.13.1)",
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
                "is_current_device": True,
            }
        },
    )

    @field_serializer("last_used_at", "created_at")
    def _en_utc(self, valor: datetime) -> str:
        """En UTC con su «Z»: sin huso, el navegador la leía como hora local (BE #737)."""
        if valor.tzinfo is None:
            return valor.isoformat() + "Z"
        return valor.astimezone(UTC).isoformat().replace("+00:00", "Z")


class ListUserDevicesRequestDTO(BaseModel):
    """
    DTO de entrada para listar dispositivos de un usuario.

    Fields:
        user_id: ID del usuario (extraído del JWT)
        user_agent: User-Agent del request HTTP (opcional, legacy) (v1.13.1)
        ip_address: IP del request HTTP (opcional, legacy) (v1.13.1)
        device_id_from_cookie: ID del dispositivo desde cookie (v2.0.4, primary identifier)
    """

    user_id: str = Field(
        ...,
        description="ID del usuario propietario de los dispositivos",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    user_agent: str | None = Field(
        default=None,
        min_length=10,
        max_length=2000,
        description="User-Agent del request HTTP (legacy, v1.13.1)",
        json_schema_extra={
            "example": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        },
    )
    ip_address: str | None = Field(
        default=None,
        min_length=7,
        max_length=45,
        description="IP del request HTTP (legacy, v1.13.1)",
        json_schema_extra={"example": "192.168.1.100"},
    )
    device_id_from_cookie: str | None = Field(
        default=None,
        min_length=36,
        max_length=36 * 5 + 4,  # hasta 5 ids separados por puntos (BE #737)
        description="ID del dispositivo desde cookie httpOnly (v2.0.4, primary identifier)",
        json_schema_extra={"example": "7c9e6679-7425-40de-944b-e07fc1f90ae7"},
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
    current_device_id: str | None = Field(
        default=None,
        description="El dispositivo desde el que se pide (el `did` del token, BE #737)",
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


class OpenSessionRequestDTO(BaseModel):
    """Abrir la sesión de un usuario ya autenticado por otra vía (BE #737)."""

    user_id: str
    user_agent: str | None = None
    ip_address: str | None = None
    device_id_from_cookie: str | None = None
    installed_app: bool = False
    country_code: str | None = Field(default=None, max_length=2)


class OpenSessionResponseDTO(BaseModel):
    """Los tokens de la sesión y el dispositivo al que pertenece."""

    access_token: str
    refresh_token: str
    device_id: str


class PurgeStaleSessionsRequestDTO(BaseModel):
    """Una limpieza a la hora `ahora` (UTC, sin huso, como el resto de fechas)."""

    ahora: datetime


class PurgeStaleSessionsResponseDTO(BaseModel):
    """Cuántos dispositivos y refrescos se borraron en una vuelta."""

    dispositivos: int
    tokens: int
