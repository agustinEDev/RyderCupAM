"""
OAuth DTOs - Application Layer

DTOs para los endpoints de Google OAuth (login, link, unlink).
"""

from pydantic import BaseModel, Field

from .user_dto import UserResponseDTO


class GoogleLoginRequestDTO(BaseModel):
    """Request DTO para login/registro con Google."""

    authorization_code: str = Field(
        ..., min_length=1, description="Authorization code de Google OAuth"
    )
    # Campos inyectados por la ruta (no vienen del body)
    ip_address: str | None = Field(None, description="IP del cliente (inyectada por la ruta)")
    user_agent: str | None = Field(None, description="User-Agent del cliente (inyectado por la ruta)")
    device_id_from_cookie: str | None = Field(
        None, description="Device ID desde cookie httpOnly (inyectado por la ruta)"
    )


class GoogleLoginResponseDTO(BaseModel):
    """Response DTO para login/registro con Google."""

    access_token: str = Field(..., description="Token JWT de acceso (15 minutos)")
    refresh_token: str = Field(..., description="Token JWT de renovación (7 días)")
    csrf_token: str = Field(..., description="Token CSRF para double-submit (15 minutos)")
    token_type: str = Field(default="bearer", description="Tipo de token (siempre 'bearer')")
    user: UserResponseDTO = Field(..., description="Información del usuario autenticado")
    is_new_user: bool = Field(
        default=False,
        description="True si el usuario fue creado en este login. Frontend debe redirigir a completar perfil.",
    )
    # Device Fingerprinting
    device_id: str | None = Field(None, description="ID del dispositivo registrado")
    should_set_device_cookie: bool = Field(
        default=False, description="True si se debe setear la cookie device_id"
    )


class LinkGoogleAccountRequestDTO(BaseModel):
    """Request DTO para vincular cuenta de Google a usuario existente."""

    authorization_code: str = Field(
        ..., min_length=1, description="Authorization code de Google OAuth"
    )


class LinkGoogleAccountResponseDTO(BaseModel):
    """Response DTO para vinculación de cuenta Google."""

    message: str = Field(..., description="Mensaje de confirmación")
    provider: str = Field(..., description="Proveedor OAuth vinculado")
    provider_email: str = Field(..., description="Email de la cuenta Google vinculada")


class UnlinkGoogleAccountResponseDTO(BaseModel):
    """Response DTO para desvinculación de cuenta Google."""

    message: str = Field(..., description="Mensaje de confirmación")
    provider: str = Field(..., description="Proveedor OAuth desvinculado")
