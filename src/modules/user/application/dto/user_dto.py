from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.shared.application.validation import (
    FieldLimits,
    NameValidator,
    sanitize_html,
)

# Literales reutilizados
CONFIRMATION_MESSAGE_DESCRIPTION = "Mensaje de confirmación."
IP_ADDRESS_DESCRIPTION = "Dirección IP del cliente (para security audit trail)."
USER_AGENT_DESCRIPTION = "User-Agent del navegador (para security audit trail)."


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

    email: EmailStr = Field(
        ..., max_length=FieldLimits.EMAIL_MAX_LENGTH, description=EMAIL_DESCRIPTION
    )
    password: str = Field(
        ...,
        min_length=12,  # Actualizado según nueva política OWASP
        max_length=FieldLimits.PASSWORD_MAX_LENGTH,
        description="Contraseña del usuario (mínimo 12 caracteres, incluir mayúsculas, minúsculas, números y símbolos).",
    )
    first_name: str = Field(
        ...,
        min_length=2,
        max_length=FieldLimits.NAME_MAX_LENGTH,
        description="Nombre del usuario.",
    )
    last_name: str = Field(
        ...,
        min_length=2,
        max_length=FieldLimits.NAME_MAX_LENGTH,
        description="Apellido del usuario.",
    )
    country_code: str | None = Field(
        None,
        min_length=2,
        max_length=2,
        pattern="^[A-Z]{2}$",
        description="Código ISO del país (2 letras mayúsculas, ej: 'ES', 'FR', 'PT'). Opcional.",
    )
    manual_handicap: float | None = Field(
        None,
        ge=-10.0,
        le=54.0,
        description="Hándicap manual (opcional). Solo se usa si no se encuentra en RFEG.",
    )
    gender: str | None = Field(
        None,
        pattern="^(MALE|FEMALE)$",
        description="Género del usuario (MALE/FEMALE). Opcional. Usado para resolución automática de tees.",
    )

    @field_validator("first_name", "last_name")
    @classmethod
    def sanitize_and_validate_name(cls, v: str) -> str:
        """Sanitiza HTML y valida formato de nombre según NameValidator."""
        # Sanitizar HTML primero
        sanitized = sanitize_html(v)
        if sanitized is None:
            raise ValueError("El nombre no puede estar vacío")

        # Validar formato de nombre (sin números ni caracteres especiales)
        return NameValidator.validate(sanitized)


# ======================================================================================
# DTO para el Caso de Uso: Buscar Usuario
# ======================================================================================


class FindUserRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de búsqueda de usuario.
    Permite buscar por email o nombre completo.
    """

    email: EmailStr | None = Field(
        None, max_length=FieldLimits.EMAIL_MAX_LENGTH, description=EMAIL_DESCRIPTION
    )
    full_name: str | None = Field(
        None,
        min_length=3,
        max_length=FieldLimits.FULL_NAME_MAX_LENGTH,
        description="Nombre completo del usuario.",
    )

    @field_validator("email", "full_name", mode="before")
    @classmethod
    def check_at_least_one_field(cls, v):
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
    handicap_updated_at: datetime | None = Field(
        None, description="Fecha y hora de la última actualización del handicap."
    )
    created_at: datetime = Field(..., description="Fecha y hora de creación del usuario.")
    updated_at: datetime = Field(..., description="Fecha y hora de la última actualización.")
    email_verified: bool = Field(
        default=False, description="Indica si el email del usuario ha sido verificado."
    )
    is_admin: bool = Field(
        default=False,
        description="Indica si el usuario tiene privilegios de administrador del sistema (RBAC).",
    )
    gender: str | None = Field(
        None,
        description="Género del usuario (MALE/FEMALE). Usado para resolución automática de tees.",
    )
    # OAuth & Auth Method fields (v2.0.10)
    auth_providers: list[str] = Field(
        default_factory=list,
        description="Proveedores OAuth vinculados al usuario (ej: ['google']). Vacío si solo usa email/password.",
    )
    has_password: bool = Field(
        default=True,
        description="True si el usuario tiene contraseña configurada. False si se registró solo con OAuth.",
    )

    # Configuración de Pydantic actualizada para V2
    model_config = ConfigDict(from_attributes=True)

    @field_validator("id", "email", "country_code", "handicap", "gender", mode="before")
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

    Security Logging (v1.8.0):
    - ip_address y user_agent son opcionales para security audit trail
    - Proporcionados por API layer, no requeridos en tests

    Device Fingerprinting (v2.0.4):
    - device_id_from_cookie: ID del dispositivo desde cookie httpOnly (primary identifier)
    """

    email: EmailStr = Field(
        ..., max_length=FieldLimits.EMAIL_MAX_LENGTH, description=EMAIL_DESCRIPTION
    )
    password: str = Field(
        ...,
        max_length=FieldLimits.PASSWORD_MAX_LENGTH,
        description="Contraseña del usuario.",
    )
    # Security context (opcional, proporcionado por API layer)
    ip_address: str | None = Field(
        None,
        max_length=45,  # IPv6 máximo: 39 chars (ej: 2001:0db8:85a3:0000:0000:8a2e:0370:7334)
        description=IP_ADDRESS_DESCRIPTION,
    )
    user_agent: str | None = Field(None, max_length=500, description=USER_AGENT_DESCRIPTION)
    # Device Fingerprinting (v2.0.4): Cookie-based identification
    device_id_from_cookie: str | None = Field(
        None,
        min_length=36,
        max_length=36,
        description="ID del dispositivo desde cookie httpOnly (v2.0.4). Primary identifier.",
    )


class LoginResponseDTO(BaseModel):
    """
    DTO de salida para el caso de uso de login.
    Devuelve el token de acceso, refresh token y la información básica del usuario.

    Session Timeout (v1.8.0):
    - access_token: Válido por 15 minutos (operaciones frecuentes)
    - refresh_token: Válido por 7 días (renovar access sin re-login)

    CSRF Protection (v1.13.0):
    - csrf_token: Token de 256 bits para validación double-submit (15 minutos)

    Device Fingerprinting (v2.0.4):
    - device_id: ID del dispositivo (para setear cookie si es nuevo)
    - should_set_device_cookie: True si el caller debe setear la cookie device_id
    """

    access_token: str = Field(..., description="Token JWT de acceso (15 minutos).")
    refresh_token: str = Field(..., description="Token JWT de renovación (7 días).")
    csrf_token: str = Field(
        ..., description="Token CSRF para validación double-submit (15 minutos)."
    )
    token_type: str = Field(default="bearer", description="Tipo de token (siempre 'bearer').")
    user: UserResponseDTO = Field(..., description="Información del usuario autenticado.")
    email_verification_required: bool = Field(
        default=False, description="Indica si el usuario necesita verificar su email."
    )
    # Device Fingerprinting (v2.0.4): Cookie-based identification
    device_id: str | None = Field(
        None,
        description="ID del dispositivo registrado (v2.0.4). Usar para setear cookie si should_set_device_cookie=True.",
    )
    should_set_device_cookie: bool = Field(
        default=False,
        description="True si el caller debe setear la cookie device_id (v2.0.4). False si la cookie ya existe.",
    )


# ======================================================================================
# DTO para el Caso de Uso: Logout
# ======================================================================================


class LogoutRequestDTO(BaseModel):
    """
    DTO de entrada para el caso de uso de logout.
    Define el token que se quiere invalidar.

    Security Logging (v1.8.0):
    - ip_address y user_agent son opcionales para security audit trail
    - Proporcionados por API layer, no requeridos en tests
    """

    # Security context (opcional, proporcionado por API layer)
    ip_address: str | None = Field(None, max_length=45, description=IP_ADDRESS_DESCRIPTION)
    user_agent: str | None = Field(None, max_length=500, description=USER_AGENT_DESCRIPTION)


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

    first_name: str | None = Field(
        None,
        min_length=2,
        max_length=FieldLimits.NAME_MAX_LENGTH,
        description="Nuevo nombre del usuario.",
    )
    last_name: str | None = Field(
        None,
        min_length=2,
        max_length=FieldLimits.NAME_MAX_LENGTH,
        description="Nuevo apellido del usuario.",
    )
    country_code: str | None = Field(
        None,
        min_length=2,
        max_length=2,
        pattern="^[A-Z]{2}$",
        description="Nuevo código ISO del país (2 letras mayúsculas, ej: 'ES', 'FR').",
    )

    @field_validator("first_name", "last_name")
    @classmethod
    def sanitize_and_validate_name(cls, v: str | None, info) -> str | None:
        """Sanitiza HTML y valida formato de nombre según NameValidator."""
        if v is None:
            return None

        # Sanitizar HTML primero
        sanitized = sanitize_html(v)
        if sanitized is None or not sanitized:
            raise ValueError(f"{info.field_name} no puede estar vacío")

        # Validar formato de nombre (sin números ni caracteres especiales)
        return NameValidator.validate(sanitized, field_name=info.field_name)

    def model_post_init(self, __context) -> None:
        """Valida que se proporcione al menos un campo."""
        if not self.first_name and not self.last_name and not self.country_code:
            raise ValueError(
                "Debe proporcionar al menos 'first_name', 'last_name' o 'country_code'."
            )


class UpdateProfileResponseDTO(BaseModel):
    """DTO de salida para actualización de perfil."""

    user: UserResponseDTO = Field(..., description="Información actualizada del usuario.")
    message: str = Field(
        default="Perfil actualizado exitosamente",
        description=CONFIRMATION_MESSAGE_DESCRIPTION,
    )


# ======================================================================================
# DTO para el Caso de Uso: Update Security
# ======================================================================================


class UpdateSecurityRequestDTO(BaseModel):
    """
    DTO de entrada para actualización de datos de seguridad (email y/o password).
    Requiere contraseña actual para verificación.

    Security Logging (v1.8.0):
    - ip_address y user_agent son opcionales para security audit trail
    - Proporcionados por API layer, no requeridos en tests
    """

    current_password: str = Field(
        ...,
        max_length=FieldLimits.PASSWORD_MAX_LENGTH,
        description="Contraseña actual (requerida).",
    )
    new_email: EmailStr | None = Field(
        None, max_length=FieldLimits.EMAIL_MAX_LENGTH, description="Nuevo email."
    )
    new_password: str | None = Field(
        None,
        min_length=12,  # Actualizado según nueva política OWASP
        max_length=FieldLimits.PASSWORD_MAX_LENGTH,
        description="Nuevo password (mínimo 12 caracteres, incluir mayúsculas, minúsculas, números y símbolos).",
    )
    confirm_password: str | None = Field(
        None,
        max_length=FieldLimits.PASSWORD_MAX_LENGTH,
        description="Confirmación del nuevo password.",
    )
    # Security context (opcional, proporcionado por API layer)
    ip_address: str | None = Field(None, max_length=45, description=IP_ADDRESS_DESCRIPTION)
    user_agent: str | None = Field(None, max_length=500, description=USER_AGENT_DESCRIPTION)

    def model_post_init(self, __context) -> None:
        """Valida que se proporcione al menos un campo y confirma password si aplica."""
        if not self.new_email and not self.new_password:
            raise ValueError("Debe proporcionar 'new_email' o 'new_password'.")

        if self.new_password and self.new_password != self.confirm_password:
            raise ValueError("El nuevo password y su confirmación no coinciden.")


class UpdateSecurityResponseDTO(BaseModel):
    """DTO de salida para actualización de seguridad."""

    user: UserResponseDTO = Field(..., description="Información actualizada del usuario.")
    message: str = Field(
        default="Datos de seguridad actualizados",
        description=CONFIRMATION_MESSAGE_DESCRIPTION,
    )


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

    message: str = Field(
        default="Email verificado exitosamente",
        description=CONFIRMATION_MESSAGE_DESCRIPTION,
    )
    email_verified: bool = Field(
        default=True, description="Confirmación de que el email fue verificado."
    )


# ======================================================================================
# DTO para el Caso de Uso: Resend Verification Email
# ======================================================================================


class ResendVerificationEmailRequestDTO(BaseModel):
    """
    DTO de entrada para reenvío de email de verificación.
    """

    email: EmailStr = Field(
        ..., max_length=FieldLimits.EMAIL_MAX_LENGTH, description=EMAIL_DESCRIPTION
    )


class ResendVerificationEmailResponseDTO(BaseModel):
    """DTO de salida para reenvío de email de verificación."""

    message: str = Field(
        default="Email de verificación enviado exitosamente",
        description=CONFIRMATION_MESSAGE_DESCRIPTION,
    )
    email: EmailStr = Field(..., description="Email al que se envió el mensaje de verificación.")


# ======================================================================================
# DTO para el Caso de Uso: Refresh Access Token (Session Timeout - v1.8.0)
# ======================================================================================


class RefreshAccessTokenRequestDTO(BaseModel):
    """
    DTO de entrada para renovar el access token usando un refresh token válido.

    Esta operación NO requiere autenticación previa, ya que el refresh token
    contiene toda la información necesaria para generar un nuevo access token.

    Security Logging (v1.8.0):
    - ip_address y user_agent son opcionales para security audit trail
    - Proporcionados por API layer, no requeridos en tests

    Device Fingerprinting (v2.0.4):
    - device_id_from_cookie: ID del dispositivo desde cookie httpOnly (primary identifier)
    """

    # El refresh token se leerá desde la cookie httpOnly, no del body
    # Security context (opcional, proporcionado por API layer)
    ip_address: str | None = Field(None, max_length=45, description=IP_ADDRESS_DESCRIPTION)
    user_agent: str | None = Field(None, max_length=500, description=USER_AGENT_DESCRIPTION)
    # Device Fingerprinting (v2.0.4): Cookie-based identification
    device_id_from_cookie: str | None = Field(
        None,
        min_length=36,
        max_length=36,
        description="ID del dispositivo desde cookie httpOnly (v2.0.4). Primary identifier.",
    )


class RefreshAccessTokenResponseDTO(BaseModel):
    """
    DTO de salida para renovación de access token.

    Retorna un nuevo access token válido por 15 minutos.
    El refresh token NO se renueva (sigue siendo el mismo hasta su expiración).

    CSRF Protection (v1.13.0):
    - csrf_token: Nuevo token CSRF generado al renovar access token (15 minutos)
    """

    access_token: str = Field(..., description="Nuevo access token JWT válido por 15 minutos.")
    csrf_token: str = Field(
        ..., description="Nuevo token CSRF para validación double-submit (15 minutos)."
    )
    token_type: str = Field(default="bearer", description="Tipo de token (siempre 'bearer').")
    user: UserResponseDTO = Field(..., description="Información básica del usuario autenticado.")
    message: str = Field(
        default="Access token renovado exitosamente",
        description="Mensaje de confirmación de renovación.",
    )
    # Device Fingerprinting (v2.0.4): Cookie-based device identification
    device_id: str | None = Field(
        default=None,
        description="ID del dispositivo registrado (para cookie httpOnly).",
    )
    should_set_device_cookie: bool = Field(
        default=False,
        description="True si el caller debe establecer la cookie device_id.",
    )


# ======================================================================================
# DTO para el Caso de Uso: Request Password Reset (Forgot Password)
# ======================================================================================


class RequestPasswordResetRequestDTO(BaseModel):
    """
    DTO de entrada para solicitar el reseteo de contraseña.

    Este endpoint es público (NO requiere autenticación) y se usa cuando el usuario
    olvida su contraseña. Se envía un email con un token único válido por 24 horas.

    Security:
    - Rate limiting: 3 intentos/hora por email (configurado en SlowAPI)
    - Timing attack prevention: Mensaje genérico sin revelar si el email existe
    - Sanitización de email para prevenir email injection
    - ip_address y user_agent opcionales para security audit trail

    Nota:
    - Si el email NO existe, se retorna 200 OK con mensaje genérico
    - Si el email existe, se envía el email y se retorna 200 OK con el mismo mensaje
    - Esto previene enumeración de usuarios (OWASP A01)
    """

    email: EmailStr = Field(
        ...,
        max_length=FieldLimits.EMAIL_MAX_LENGTH,
        description="Email del usuario que solicita resetear su contraseña.",
    )
    # Security context (opcional, proporcionado por API layer)
    ip_address: str | None = Field(None, max_length=45, description=IP_ADDRESS_DESCRIPTION)
    user_agent: str | None = Field(None, max_length=500, description=USER_AGENT_DESCRIPTION)


class RequestPasswordResetResponseDTO(BaseModel):
    """
    DTO de salida para solicitud de reseteo de contraseña.

    IMPORTANTE: El mensaje es genérico para prevenir enumeración de usuarios.
    No revela si el email existe o no en el sistema.
    """

    message: str = Field(
        default="Si el email existe en nuestro sistema, recibirás un enlace para resetear tu contraseña.",
        description="Mensaje genérico de confirmación (no revela si el email existe).",
    )
    email: EmailStr = Field(..., description="Email al que se envió el enlace (si existe).")


# ======================================================================================
# DTO para el Caso de Uso: Reset Password (Completar Reseteo)
# ======================================================================================


class ResetPasswordRequestDTO(BaseModel):
    """
    DTO de entrada para completar el reseteo de contraseña.

    Este endpoint es público (NO requiere autenticación) y se usa cuando el usuario
    hace clic en el enlace del email de reseteo.

    Validaciones:
    - Token debe ser válido y no expirado (< 24 horas)
    - Nueva contraseña debe cumplir política OWASP ASVS V2.1:
      * Mínimo 12 caracteres
      * Al menos 1 mayúscula, 1 minúscula, 1 número, 1 símbolo
      * No en lista de contraseñas comunes

    Post-Condiciones:
    - Token invalidado (uso único)
    - Todas las sesiones activas del usuario invalidadas (refresh tokens revocados)
    - Email de confirmación enviado al usuario

    Security:
    - Rate limiting: 3 intentos/hora por IP (configurado en SlowAPI)
    - Token de un solo uso (se invalida después del primer uso exitoso)
    - Password policy aplicada por el Value Object Password
    - ip_address y user_agent opcionales para security audit trail
    """

    token: str = Field(
        ...,
        min_length=32,
        max_length=100,
        description="Token de reseteo único recibido por email (válido 24 horas).",
    )
    new_password: str = Field(
        ...,
        min_length=12,
        max_length=FieldLimits.PASSWORD_MAX_LENGTH,
        description="Nueva contraseña (mínimo 12 caracteres, incluir mayúsculas, minúsculas, números y símbolos).",
    )
    # Security context (opcional, proporcionado por API layer)
    ip_address: str | None = Field(None, max_length=45, description=IP_ADDRESS_DESCRIPTION)
    user_agent: str | None = Field(None, max_length=500, description=USER_AGENT_DESCRIPTION)


class ResetPasswordResponseDTO(BaseModel):
    """
    DTO de salida para reseteo de contraseña completado.

    Confirma que la contraseña fue cambiada exitosamente.
    """

    message: str = Field(
        default="Contraseña reseteada exitosamente. Todas tus sesiones activas han sido cerradas por seguridad.",
        description="Mensaje de confirmación de reseteo exitoso.",
    )
    email: EmailStr = Field(..., description="Email del usuario que completó el reseteo.")


# ======================================================================================
# DTO para el Caso de Uso: Validate Reset Token (Validación Previa - Opcional)
# ======================================================================================


class ValidateResetTokenRequestDTO(BaseModel):
    """
    DTO de entrada para validar un token de reseteo antes de mostrar el formulario.

    Este endpoint es OPCIONAL pero mejora la UX:
    - Valida el token ANTES de que el usuario complete el formulario
    - Si el token es inválido/expirado, redirige a /forgot-password con mensaje
    - Si el token es válido, muestra el formulario de nueva contraseña

    Security:
    - NO requiere autenticación (endpoint público)
    - NO revela información sobre el usuario (solo valida token)
    - Rate limiting: 10 intentos/hora por IP
    """

    token: str = Field(
        ..., min_length=32, max_length=100, description="Token de reseteo a validar."
    )


class ValidateResetTokenResponseDTO(BaseModel):
    """
    DTO de salida para validación de token de reseteo.

    Retorna si el token es válido y no ha expirado.
    """

    valid: bool = Field(..., description="True si el token es válido y no expiró.")
    message: str = Field(..., description="Mensaje descriptivo del estado del token.")
    # NO incluir email del usuario por seguridad (no revelar información)


# ======================================================================================
# DTOs para Account Lockout (v1.13.0)
# ======================================================================================


class UnlockAccountRequestDTO(BaseModel):
    """
    DTO de entrada para desbloquear manualmente una cuenta (solo Admin).

    Security (OWASP A01, A09):
    - Solo Admin puede ejecutar este endpoint
    - Se registra quién desbloqueó en AccountUnlockedEvent
    """

    user_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="UUID del usuario cuya cuenta se va a desbloquear.",
    )
    unlocked_by_user_id: str = Field(
        ...,
        min_length=36,
        max_length=36,
        description="UUID del admin que realiza el desbloqueo (para auditoría).",
    )


class UnlockAccountResponseDTO(BaseModel):
    """
    DTO de salida para desbloqueo de cuenta.

    Retorna el resultado de la operación de desbloqueo.
    """

    success: bool = Field(..., description="True si la cuenta fue desbloqueada exitosamente.")
    message: str = Field(..., description="Mensaje descriptivo del resultado.")
    user_id: str = Field(..., description="UUID del usuario cuya cuenta fue desbloqueada.")
    unlocked_by: str = Field(..., description="UUID del admin que realizó el desbloqueo.")


# ======================================================================================
# DTO para Consultar Roles de Usuario (RBAC)
# ======================================================================================


class UserRolesResponseDTO(BaseModel):
    """
    DTO de salida que indica los roles del usuario en una competición específica.

    Utilizado por el frontend para mostrar/ocultar funcionalidades según permisos.
    """

    is_admin: bool = Field(
        ..., description="True si el usuario es administrador del sistema (rol global)."
    )
    is_creator: bool = Field(
        ..., description="True si el usuario creó esta competición (rol contextual)."
    )
    is_player: bool = Field(
        ...,
        description="True si el usuario está enrollado en esta competición con status APPROVED (rol contextual).",
    )
    competition_id: str = Field(
        ..., description="UUID de la competición para la cual se consultaron los roles."
    )
