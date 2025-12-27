"""
🔐 Security Events - Eventos de Dominio para Auditoría de Seguridad

Eventos especializados para trazabilidad completa de acciones críticas
de seguridad según OWASP A09 (Security Logging and Monitoring).

Características:
- Eventos inmutables con toda la información de contexto
- Severity levels para priorización
- Metadatos enriquecidos (IP, User-Agent, timestamp)
- Integración con correlation IDs
- Cumplimiento OWASP Top 10 2021
"""

from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from .domain_event import DomainEvent


class SecuritySeverity(Enum):
    """Niveles de severidad para eventos de seguridad"""
    CRITICAL = "CRITICAL"  # Intentos de breach, cambios críticos
    HIGH = "HIGH"          # Login fallidos repetidos, cambios de seguridad
    MEDIUM = "MEDIUM"      # Login exitoso, cambios de perfil
    LOW = "LOW"            # Acciones de consulta


@dataclass(frozen=True)
class SecurityAuditEvent(DomainEvent, ABC):
    """
    Clase base abstracta para eventos de auditoría de seguridad.

    Todos los eventos de seguridad heredan de esta clase y contienen
    información de contexto completa para trazabilidad.

    Atributos:
        user_id: ID del usuario (None si no autenticado)
        ip_address: Dirección IP del cliente
        user_agent: User-Agent del navegador
        severity: Nivel de severidad del evento
    """
    user_id: str | None
    ip_address: str
    user_agent: str
    severity: SecuritySeverity = SecuritySeverity.MEDIUM

    def __post_init__(self):
        """Validación básica de campos requeridos"""
        if not self.ip_address:
            raise ValueError("ip_address es requerido en SecurityAuditEvent")
        if not self.user_agent:
            raise ValueError("user_agent es requerido en SecurityAuditEvent")

    @property
    def aggregate_type(self) -> str:
        """Tipo de agregado (Security para eventos de seguridad)"""
        return "Security"

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa el evento a diccionario para logging.

        Returns:
            Diccionario con todos los campos del evento
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.__class__.__name__,
            "occurred_on": self.occurred_on.isoformat(),
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "severity": self.severity.value,
            "aggregate_type": self.aggregate_type,
        }


# ============================================================================
# AUTHENTICATION EVENTS
# ============================================================================

@dataclass(frozen=True)
class LoginAttemptEvent(SecurityAuditEvent):
    """
    Evento de intento de login (exitoso o fallido).

    Se emite en cada intento de autenticación para trazabilidad completa
    de accesos al sistema y detección de patrones de ataque.

    Atributos:
        email: Email usado en el intento de login
        success: Si el login fue exitoso
        failure_reason: Razón del fallo (None si exitoso)

    Ejemplos de failure_reason:
        - "Invalid credentials"
        - "Account locked"
        - "Email not verified"
        - "User not found"
    """
    email: str = ""  # Requerido, validado en __post_init__
    success: bool = False  # Requerido, pero con default para dataclass
    failure_reason: str | None = None

    def __post_init__(self):
        """Validación de campos"""
        super().__post_init__()
        if not self.email:
            raise ValueError("email es requerido en LoginAttemptEvent")

        # Si falló, debe haber una razón
        if not self.success and not self.failure_reason:
            raise ValueError("failure_reason es requerido cuando success=False")

        # Ajustar severity según resultado
        if not self.success:
            # Login fallido es HIGH (posible ataque)
            object.__setattr__(self, 'severity', SecuritySeverity.HIGH)
        else:
            # Login exitoso es MEDIUM (evento normal)
            object.__setattr__(self, 'severity', SecuritySeverity.MEDIUM)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "email": self.email,
            "success": self.success,
            "failure_reason": self.failure_reason,
        })
        return base


@dataclass(frozen=True)
class LogoutEvent(SecurityAuditEvent):
    """
    Evento de logout explícito por parte del usuario.

    Registra cuando un usuario cierra sesión correctamente,
    incluyendo la revocación de refresh tokens.

    Atributos:
        refresh_tokens_revoked: Número de refresh tokens revocados
    """
    refresh_tokens_revoked: int = 0

    def __post_init__(self):
        """Validación y configuración de severity"""
        super().__post_init__()
        # Logout es evento de baja severidad (acción normal)
        object.__setattr__(self, 'severity', SecuritySeverity.LOW)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "refresh_tokens_revoked": self.refresh_tokens_revoked,
        })
        return base


@dataclass(frozen=True)
class RefreshTokenUsedEvent(SecurityAuditEvent):
    """
    Evento de uso de refresh token para renovar access token.

    Registra cuando un usuario renueva su access token usando un
    refresh token válido. Útil para detectar uso anómalo de tokens.

    Atributos:
        refresh_token_id: ID del refresh token usado
        new_access_token_created: Si se creó exitosamente un nuevo access token
    """
    refresh_token_id: str = ""  # Requerido, validado en __post_init__
    new_access_token_created: bool = True

    def __post_init__(self):
        """Validación y configuración de severity"""
        super().__post_init__()
        if not self.refresh_token_id:
            raise ValueError("refresh_token_id es requerido en RefreshTokenUsedEvent")

        # Uso de refresh token es LOW (acción normal)
        object.__setattr__(self, 'severity', SecuritySeverity.LOW)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "refresh_token_id": self.refresh_token_id,
            "new_access_token_created": self.new_access_token_created,
        })
        return base


@dataclass(frozen=True)
class RefreshTokenRevokedEvent(SecurityAuditEvent):
    """
    Evento de revocación de refresh tokens (logout).

    Registra cuando se revocan uno o más refresh tokens de un usuario,
    típicamente durante logout o cambio de contraseña.

    Atributos:
        tokens_revoked_count: Cantidad de tokens revocados
        reason: Razón de la revocación ("logout", "password_change", "security_breach")
    """
    tokens_revoked_count: int = 0  # Requerido, validado en __post_init__
    reason: str = ""  # Requerido, validado en __post_init__

    def __post_init__(self):
        """Validación y configuración de severity"""
        super().__post_init__()
        if self.tokens_revoked_count < 0:
            raise ValueError("tokens_revoked_count no puede ser negativo")
        if not self.reason:
            raise ValueError("reason es requerido en RefreshTokenRevokedEvent")

        # Revocación por security breach es CRITICAL
        if self.reason == "security_breach":
            object.__setattr__(self, 'severity', SecuritySeverity.CRITICAL)
        # Revocación por password change es HIGH
        elif self.reason == "password_change":
            object.__setattr__(self, 'severity', SecuritySeverity.HIGH)
        # Revocación por logout normal es LOW
        else:
            object.__setattr__(self, 'severity', SecuritySeverity.LOW)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "tokens_revoked_count": self.tokens_revoked_count,
            "reason": self.reason,
        })
        return base


# ============================================================================
# ACCOUNT SECURITY EVENTS
# ============================================================================

@dataclass(frozen=True)
class PasswordChangedEvent(SecurityAuditEvent):
    """
    Evento de cambio de contraseña exitoso.

    Registra cuando un usuario cambia su contraseña, incluyendo si
    la contraseña anterior era correcta (cambio normal vs reset).

    Atributos:
        old_password_verified: Si se verificó la contraseña anterior (True = cambio normal)
    """
    old_password_verified: bool = True

    def __post_init__(self):
        """Validación y configuración de severity"""
        super().__post_init__()
        # Cambio de contraseña es HIGH (acción de seguridad importante)
        object.__setattr__(self, 'severity', SecuritySeverity.HIGH)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "old_password_verified": self.old_password_verified,
        })
        return base


@dataclass(frozen=True)
class EmailChangedEvent(SecurityAuditEvent):
    """
    Evento de cambio de email exitoso.

    Registra cuando un usuario cambia su dirección de email.
    Por privacidad, NO guardamos el email anterior ni el nuevo.

    Atributos:
        email_verification_required: Si requiere verificación del nuevo email
    """
    email_verification_required: bool = True

    def __post_init__(self):
        """Validación y configuración de severity"""
        super().__post_init__()
        # Cambio de email es HIGH (acción de seguridad importante)
        object.__setattr__(self, 'severity', SecuritySeverity.HIGH)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "email_verification_required": self.email_verification_required,
        })
        return base


# ============================================================================
# ACCESS CONTROL EVENTS
# ============================================================================

@dataclass(frozen=True)
class AccessDeniedEvent(SecurityAuditEvent):
    """
    Evento de acceso denegado (HTTP 403).

    Registra cuando un usuario autenticado intenta acceder a un recurso
    para el cual no tiene permisos. Útil para detectar intentos de
    escalación de privilegios.

    Atributos:
        resource_type: Tipo de recurso al que intentó acceder ("competition", "enrollment", etc.)
        resource_id: ID del recurso (None si no aplica)
        action_attempted: Acción que intentó realizar ("update", "delete", "approve", etc.)
        denial_reason: Razón del rechazo ("not_creator", "not_enrolled", etc.)
    """
    resource_type: str = ""  # Requerido, validado en __post_init__
    resource_id: str | None = None
    action_attempted: str = ""  # Requerido, validado en __post_init__
    denial_reason: str = ""  # Requerido, validado en __post_init__

    def __post_init__(self):
        """Validación y configuración de severity"""
        super().__post_init__()
        if not self.resource_type:
            raise ValueError("resource_type es requerido en AccessDeniedEvent")
        if not self.action_attempted:
            raise ValueError("action_attempted es requerido en AccessDeniedEvent")
        if not self.denial_reason:
            raise ValueError("denial_reason es requerido en AccessDeniedEvent")

        # Acceso denegado es HIGH (posible intento malicioso)
        object.__setattr__(self, 'severity', SecuritySeverity.HIGH)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action_attempted": self.action_attempted,
            "denial_reason": self.denial_reason,
        })
        return base


@dataclass(frozen=True)
class RateLimitExceededEvent(SecurityAuditEvent):
    """
    Evento de rate limiting activado (HTTP 429).

    Registra cuando un cliente excede los límites de tasa configurados,
    lo cual puede indicar uso abusivo o ataque automatizado.

    Atributos:
        endpoint: Endpoint que alcanzó el límite (ej: "/api/v1/auth/login")
        limit_type: Tipo de límite ("per_minute", "per_hour", "global")
        limit_value: Valor del límite (ej: "5/minute")
        request_count: Número de requests realizados
    """
    endpoint: str = ""  # Requerido, validado en __post_init__
    limit_type: str = ""  # Requerido, validado en __post_init__
    limit_value: str = ""
    request_count: int = 0  # Requerido, validado en __post_init__

    def __post_init__(self):
        """Validación y configuración de severity"""
        super().__post_init__()
        if not self.endpoint:
            raise ValueError("endpoint es requerido en RateLimitExceededEvent")
        if not self.limit_type:
            raise ValueError("limit_type es requerido en RateLimitExceededEvent")
        if self.request_count < 0:
            raise ValueError("request_count no puede ser negativo")

        # Rate limit excedido es MEDIUM (puede ser uso legítimo intenso)
        object.__setattr__(self, 'severity', SecuritySeverity.MEDIUM)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "endpoint": self.endpoint,
            "limit_type": self.limit_type,
            "limit_value": self.limit_value,
            "request_count": self.request_count,
        })
        return base


# ============================================================================
# PASSWORD RESET EVENTS
# ============================================================================

@dataclass(frozen=True)
class PasswordResetRequestedAuditEvent(SecurityAuditEvent):
    """
    Evento de auditoría para solicitud de reseteo de contraseña.

    Se emite cuando un usuario solicita resetear su contraseña a través del
    formulario "Olvidé mi contraseña". Este evento se registra SIEMPRE,
    incluso si el email no existe (para auditoría completa).

    Atributos:
        email: Email usado en la solicitud
        success: Si el email existe y se envió el enlace
        failure_reason: Razón del fallo (None si exitoso)

    Ejemplos de failure_reason:
        - "Email not found (not revealed to client)"
        - "Rate limit exceeded"
        - "Email service unavailable"

    Security:
        - Permite detectar intentos masivos de enumeración de usuarios
        - success=False NO se revela al cliente (mensaje genérico)
        - Timing attack prevention con delay artificial
    """
    email: str = ""  # Requerido, validado en __post_init__
    success: bool = False  # Requerido, pero con default para dataclass
    failure_reason: str | None = None

    def __post_init__(self):
        """Validación y asignación de severity según éxito/fallo"""
        super().__post_init__()

        # Validar email
        if not self.email or '@' not in self.email:
            raise ValueError("email debe ser válido")

        # Si falló, debe haber una razón (auditoría completa)
        if not self.success and not self.failure_reason:
            raise ValueError("failure_reason es requerido cuando success=False")

        # Severity:
        # - Fallido = HIGH (posible ataque de enumeración)
        # - Exitoso = MEDIUM (operación normal)
        if self.success:
            object.__setattr__(self, 'severity', SecuritySeverity.MEDIUM)
        else:
            object.__setattr__(self, 'severity', SecuritySeverity.HIGH)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "email": self.email,
            "success": self.success,
            "failure_reason": self.failure_reason,
        })
        return base


@dataclass(frozen=True)
class PasswordResetCompletedAuditEvent(SecurityAuditEvent):
    """
    Evento de auditoría para reseteo de contraseña completado.

    Se emite cuando un usuario completa exitosamente el reseteo de su contraseña
    usando el token del email. Este evento es crítico para auditoría de seguridad.

    Atributos:
        email: Email del usuario que reseteó la contraseña
        success: Si el reseteo fue exitoso
        failure_reason: Razón del fallo (None si exitoso)

    Ejemplos de failure_reason:
        - "Invalid or expired token"
        - "Password does not meet policy"
        - "Token already used"

    Security:
        - Permite detectar cambios de contraseña no autorizados
        - success=True trigger para invalidar TODAS las sesiones activas
        - Email de notificación enviado al usuario
        - Severity HIGH/CRITICAL según contexto

    Post-Conditions (si success=True):
        - Token invalidado (uso único)
        - Todos los refresh tokens revocados
        - Email de confirmación enviado
    """
    email: str = ""  # Requerido, validado en __post_init__
    success: bool = False  # Requerido, pero con default para dataclass
    failure_reason: str | None = None

    def __post_init__(self):
        """Validación y asignación de severity según éxito/fallo"""
        super().__post_init__()

        # Validar email
        if not self.email or '@' not in self.email:
            raise ValueError("email debe ser válido")

        # Si falló, debe haber una razón (auditoría completa)
        if not self.success and not self.failure_reason:
            raise ValueError("failure_reason es requerido cuando success=False")

        # Severity:
        # - Exitoso = HIGH (cambio de seguridad importante)
        # - Fallido = MEDIUM (intento fallido normal)
        if self.success:
            object.__setattr__(self, 'severity', SecuritySeverity.HIGH)
        else:
            object.__setattr__(self, 'severity', SecuritySeverity.MEDIUM)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update({
            "email": self.email,
            "success": self.success,
            "failure_reason": self.failure_reason,
        })
        return base
