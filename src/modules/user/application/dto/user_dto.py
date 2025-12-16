from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Literales reutilizados
CONFIRMATION_MESSAGE_DESCRIPTION = "Mensaje de confirmación."


# Constants
EMAIL_DESCRIPTION = "Correo electrónico del usuario."


# ======================================================================================
# DTO para el Caso de Uso: Registrar Usuario
# ======================================================================================

class RegisterUserRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de registro de usuario.
    Define los datos necesarios para crear un nuevo usuario.
    """
    email: EmailStr = Field(..., description=EMAIL_DESCRIPTION)
    password: str = Field(..., min_length=8, description="Contraseña del usuario (mínimo 8 caracteres).")
    first_name: str = Field(..., min_length=2, description="Nombre del usuario.")
    last_name: str = Field(..., min_length=2, description="Apellido del usuario.")
    country_code: str | None = Field(
        None,
        min_length=2,
        max_length=2,
        pattern="^[A-Z]{2}$",
        description="Código ISO del país (2 letras mayúsculas, ej: 'ES', 'FR', 'PT'). Opcional."
    )
    manual_handicap: float | None = Field(
        None,
        ge=-10.0,
        le=54.0,
        description="Hándicap manual (opcional). Solo se usa si no se encuentra en RFEG."
    )

# ======================================================================================
# DTO para el Caso de Uso: Buscar Usuario
# ======================================================================================

class FindUserRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de búsqueda de usuario.
    Permite buscar por email o nombre completo.
    """
    email: EmailStr | None = Field(None, description=EMAIL_DESCRIPTION)
    full_name: str | None = Field(None, min_length=3, description="Nombre completo del usuario.")

    @field_validator('email', 'full_name', mode='before')
    @classmethod
    def check_at_least_one_field(cls, v, info):
        """Valida que se proporcione al menos un campo de búsqueda."""
        return v

    def model_post_init(self, __context) -> None:
        """Valida que se proporcione al menos un criterio de búsqueda."""
        if not self.email and not self.full_name:
            raise ValueError("Debe proporcionar al menos 'email' o 'full_name' para la búsqueda.")

class FindUserResponseDTO(BaseModel):
    """
    DTO de respuesta para el caso de uso de búsqueda de usuario.
    Devuelve información básica del usuario encontrado.
    """
    user_id: UUID = Field(..., description="ID único del usuario encontrado.")
    email: EmailStr = Field(..., description=EMAIL_DESCRIPTION)
    full_name: str = Field(..., description="Nombre completo del usuario.")

    # Configuración de Pydantic actualizada para V2
    model_config = ConfigDict(from_attributes=True)

# ======================================================================================
# DTO de Respuesta Genérico para el Usuario
# ======================================================================================

class UserResponseDTO(BaseModel):
    """
    DTO de salida que representa a un usuario.
    Se utiliza para devolver información del usuario de forma segura (sin contraseña).
    """
    id: UUID = Field(..., description="ID único del usuario.")
    email: EmailStr = Field(..., description=EMAIL_DESCRIPTION)
    first_name: str = Field(..., description="Nombre del usuario.")
    last_name: str = Field(..., description="Apellido del usuario.")
    country_code: str | None = Field(None, description="Código ISO del país (2 letras, ej: 'ES').")
    handicap: float | None = Field(None, description="Handicap de golf del usuario.")
    handicap_updated_at: datetime | None = Field(None, description="Fecha y hora de la última actualización del handicap.")
    created_at: datetime = Field(..., description="Fecha y hora de creación del usuario.")
    updated_at: datetime = Field(..., description="Fecha y hora de la última actualización.")
    email_verified: bool = Field(default=False, description="Indica si el email del usuario ha sido verificado.")

    # Configuración de Pydantic actualizada para V2
    model_config = ConfigDict(from_attributes=True)

    @field_validator("id", "email", "country_code", "handicap", mode="before")
    @classmethod
    def convert_value_objects(cls, v):
        """
        Convierte nuestros Value Objects a tipos primitivos que Pydantic entiende.
        Se ejecuta ANTES de la validación estándar de Pydantic.
        """
        # Si el valor 'v' tiene un atributo 'value', usamos ese valor.
        # Esto funciona para UserId, Email, CountryCode y Handicap.
        if hasattr(v, "value"):
            return v.value
        return v


# ======================================================================================
# DTO para el Caso de Uso: Login
# ======================================================================================

class LoginRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de login.
    Define las credenciales necesarias para autenticar un usuario.
    """
    email: EmailStr = Field(..., description=EMAIL_DESCRIPTION)
    password: str = Field(..., description="Contraseña del usuario.")


class LoginResponseDTO(BaseModel):
    """
    DTO de salida para el caso de uso de login.
    Devuelve el token de acceso, refresh token y la información básica del usuario.

    Session Timeout (v1.8.0):
    - access_token: Válido por 15 minutos (operaciones frecuentes)
    - refresh_token: Válido por 7 días (renovar access sin re-login)
    """
    access_token: str = Field(..., description="Token JWT de acceso (15 minutos).")
    refresh_token: str = Field(..., description="Token JWT de renovación (7 días).")
    token_type: str = Field(default="bearer", description="Tipo de token (siempre 'bearer').")
    user: UserResponseDTO = Field(..., description="Información del usuario autenticado.")
    email_verification_required: bool = Field(default=False, description="Indica si el usuario necesita verificar su email.")


# ======================================================================================
# DTO para el Caso de Uso: Logout
# ======================================================================================

class LogoutRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de logout.
    Define el token que se quiere invalidar.
    """
    # Nota: El token se obtiene del header Authorization, no del body
    # Este DTO queda preparado para futuras extensiones
    pass


class LogoutResponseDTO(BaseModel):
    """
    DTO de salida para el caso de uso de logout.
    Confirma que el logout se realizó correctamente.
    """
    message: str = Field(default="Logout exitoso", description=CONFIRMATION_MESSAGE_DESCRIPTION)
    logged_out_at: datetime = Field(..., description="Timestamp del logout.")


# ======================================================================================
# DTO para el Caso de Uso: Update Profile
# ======================================================================================

class UpdateProfileRequestDTO(BaseModel):
    """
    DTO de entrada para actualización de información personal del usuario.
    Al menos uno de los campos debe ser proporcionado.
    """
    first_name: str | None = Field(None, min_length=2, description="Nuevo nombre del usuario.")
    last_name: str | None = Field(None, min_length=2, description="Nuevo apellido del usuario.")
    country_code: str | None = Field(
        None,
        min_length=2,
        max_length=2,
        pattern="^[A-Z]{2}$",
        description="Nuevo código ISO del país (2 letras mayúsculas, ej: 'ES', 'FR')."
    )

    def model_post_init(self, __context) -> None:
        """Valida que se proporcione al menos un campo."""
        if not self.first_name and not self.last_name and not self.country_code:
            raise ValueError("Debe proporcionar al menos 'first_name', 'last_name' o 'country_code'.")


class UpdateProfileResponseDTO(BaseModel):
    """DTO de salida para actualización de perfil."""
    user: UserResponseDTO = Field(..., description="Información actualizada del usuario.")
    message: str = Field(default="Perfil actualizado exitosamente", description=CONFIRMATION_MESSAGE_DESCRIPTION)


# ======================================================================================
# DTO para el Caso de Uso: Update Security
# ======================================================================================

class UpdateSecurityRequestDTO(BaseModel):
    """
    DTO de entrada para actualización de datos de seguridad (email y/o password).
    Requiere contraseña actual para verificación.
    """
    current_password: str = Field(..., min_length=8, description="Contraseña actual (requerida).")
    new_email: EmailStr | None = Field(None, description="Nuevo email.")
    new_password: str | None = Field(None, min_length=8, description="Nuevo password.")
    confirm_password: str | None = Field(None, description="Confirmación del nuevo password.")

    def model_post_init(self, __context) -> None:
        """Valida que se proporcione al menos un campo y confirma password si aplica."""
        if not self.new_email and not self.new_password:
            raise ValueError("Debe proporcionar 'new_email' o 'new_password'.")

        if self.new_password and self.new_password != self.confirm_password:
            raise ValueError("El nuevo password y su confirmación no coinciden.")


class UpdateSecurityResponseDTO(BaseModel):
    """DTO de salida para actualización de seguridad."""
    user: UserResponseDTO = Field(..., description="Información actualizada del usuario.")
    message: str = Field(default="Datos de seguridad actualizados", description=CONFIRMATION_MESSAGE_DESCRIPTION)


# ======================================================================================
# DTO para el Caso de Uso: Verify Email
# ======================================================================================

class VerifyEmailRequestDTO(BaseModel):
    """
    DTO de entrada para verificación de email.
    """
    token: str = Field(..., min_length=1, description="Token de verificación de email.")


class VerifyEmailResponseDTO(BaseModel):
    """DTO de salida para verificación de email."""
    message: str = Field(default="Email verificado exitosamente", description=CONFIRMATION_MESSAGE_DESCRIPTION)
    email_verified: bool = Field(default=True, description="Confirmación de que el email fue verificado.")


# ======================================================================================
# DTO para el Caso de Uso: Resend Verification Email
# ======================================================================================

class ResendVerificationEmailRequestDTO(BaseModel):
    """
    DTO de entrada para reenvío de email de verificación.
    """
    email: EmailStr = Field(..., description=EMAIL_DESCRIPTION)


class ResendVerificationEmailResponseDTO(BaseModel):
    """DTO de salida para reenvío de email de verificación."""
    message: str = Field(default="Email de verificación enviado exitosamente", description=CONFIRMATION_MESSAGE_DESCRIPTION)
    email: EmailStr = Field(..., description="Email al que se envió el mensaje de verificación.")


# ======================================================================================
# DTO para el Caso de Uso: Refresh Access Token (Session Timeout - v1.8.0)
# ======================================================================================

class RefreshAccessTokenRequestDTO(BaseModel):
    """
    DTO de entrada para renovar el access token usando un refresh token válido.

    Esta operación NO requiere autenticación previa, ya que el refresh token
    contiene toda la información necesaria para generar un nuevo access token.
    """
    # El refresh token se leerá desde la cookie httpOnly, no del body
    # Este DTO está vacío pero sirve como contrato del caso de uso
    pass


class RefreshAccessTokenResponseDTO(BaseModel):
    """
    DTO de salida para renovación de access token.

    Retorna un nuevo access token válido por 15 minutos.
    El refresh token NO se renueva (sigue siendo el mismo hasta su expiración).
    """
    access_token: str = Field(..., description="Nuevo access token JWT válido por 15 minutos.")
    token_type: str = Field(default="bearer", description="Tipo de token (siempre 'bearer').")
    user: UserResponseDTO = Field(..., description="Información básica del usuario autenticado.")
    message: str = Field(
        default="Access token renovado exitosamente",
        description="Mensaje de confirmación de renovación."
    )
