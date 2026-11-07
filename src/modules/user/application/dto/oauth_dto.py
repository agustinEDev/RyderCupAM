"""
OAuth DTOs - Application Layer

DTOs para los endpoints de Google OAuth (login, link, unlink).
"""

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from .user_dto import UserResponseDTO


class GoogleLoginRequestDTO(BaseModel):
    """Request DTO para login/registro con Google."""

    authorization_code: str = Field(
        ..., min_length=1, description="Authorization code de Google OAuth"
    )
    # Campos inyectados por la ruta (no vienen del body)
    ip_address: str | None = Field(None, description="IP del cliente (inyectada por la ruta)")
    user_agent: str | None = Field(
        None, description="User-Agent del cliente (inyectado por la ruta)"
    )
    device_id_from_cookie: str | None = Field(
        None, description="Device ID desde cookie httpOnly (inyectado por la ruta)"
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
    # El dispositivo de la sesión: toda sesión tiene uno (BE #737)
    device_id: str = Field(..., description="ID del dispositivo de esta sesión")


class ReauthenticateRequestDTO(BaseModel):
    """La contraseña actual, antes de vincular Google (BE #753)."""

    password: str = Field(..., min_length=1, max_length=128, description="Contraseña actual")
    # Para el log de seguridad: la ruta los pone desde la petición; lo del cliente no cuenta
    ip_address: SkipJsonSchema[str | None] = Field(default=None, max_length=45)
    user_agent: SkipJsonSchema[str | None] = Field(default=None, max_length=500)


class ReauthenticateResponseDTO(BaseModel):
    """La marca queda en una cookie httpOnly; aquí, cuánto dura."""

    expires_in: int = Field(..., description="Segundos que vale la marca")


class LinkGoogleAccountRequestDTO(BaseModel):
    """Request DTO para vincular cuenta de Google a usuario existente."""

    authorization_code: str = Field(
        ..., min_length=1, description="Authorization code de Google OAuth"
    )
    # Para el log de seguridad (#750 punto 3): la ruta los pone siempre desde la
    # petición, como en el login; lo que mande el cliente no cuenta
    # Fuera del esquema público, como en el desbloqueo
    ip_address: SkipJsonSchema[str | None] = Field(default=None, max_length=45)
    user_agent: SkipJsonSchema[str | None] = Field(default=None, max_length=500)


class LinkGoogleAccountResponseDTO(BaseModel):
    """Response DTO para vinculación de cuenta Google."""

    message: str = Field(..., description="Mensaje de confirmación")
    provider: str = Field(..., description="Proveedor OAuth vinculado")
    provider_email: str = Field(..., description="Email de la cuenta Google vinculada")


class UnlinkGoogleAccountResponseDTO(BaseModel):
    """Response DTO para desvinculación de cuenta Google."""

    message: str = Field(..., description="Mensaje de confirmación")
    provider: str = Field(..., description="Proveedor OAuth desvinculado")
