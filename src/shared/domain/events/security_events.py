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
from enum import Enum
from typing import Any

from .domain_event import DomainEvent


class SecuritySeverity(Enum):
    """Niveles de severidad para eventos de seguridad"""

    CRITICAL = "CRITICAL"  # Intentos de breach, cambios críticos
    HIGH = "HIGH"  # Login fallidos repetidos, cambios de seguridad
    MEDIUM = "MEDIUM"  # Login exitoso, cambios de perfil
    LOW = "LOW"  # Acciones de consulta


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

    def resumen(self, user_info: str) -> str | None:
        """La línea del log, si el evento la sabe dar (BE #732, #733, #744)."""
        return None

    @property
    def is_failure(self) -> bool:
        """
        Si el evento cuenta que algo salió mal (BE #229).

        Es otro eje que la severidad: un cambio de contraseña es HIGH para la
        auditoría y no es un fallo. Por defecto, éxito; cada evento que puede
        fallar lo redefine. No entra en to_dict: el registro no cambia.
        """
        return False

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
            object.__setattr__(self, "severity", SecuritySeverity.HIGH)
        else:
            # Login exitoso es MEDIUM (evento normal)
            object.__setattr__(self, "severity", SecuritySeverity.MEDIUM)

    @property
    def is_failure(self) -> bool:
        """Fallo cuando no tuvo éxito"""
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "email": self.email,
                "success": self.success,
                "failure_reason": self.failure_reason,
            }
        )
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
        object.__setattr__(self, "severity", SecuritySeverity.LOW)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "refresh_tokens_revoked": self.refresh_tokens_revoked,
            }
        )
        return base


@dataclass(frozen=True)
class TermsAcceptedEvent(SecurityAuditEvent):
    """
    Evento de aceptación de los Términos de uso.

    Se emite cada vez que un usuario acepta de verdad una versión (en el
    registro o en POST /users/me/accept-terms); volver a aceptar la que ya
    tenía no lo emite. Es el rastro de auditoría del consentimiento, junto a
    la tabla terms_acceptances.

    Atributos:
        terms_version: La versión aceptada
    """

    terms_version: str = ""

    def __post_init__(self):
        """Validación y severidad: aceptar es una acción normal"""
        super().__post_init__()
        if not self.terms_version:
            raise ValueError("terms_version es requerido en TermsAcceptedEvent")
        object.__setattr__(self, "severity", SecuritySeverity.LOW)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con la versión aceptada"""
        base = super().to_dict()
        base.update({"terms_version": self.terms_version})
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
        object.__setattr__(self, "severity", SecuritySeverity.LOW)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "refresh_token_id": self.refresh_token_id,
                "new_access_token_created": self.new_access_token_created,
            }
        )
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
    # Qué dispositivo se revocó, cuando es una revocación de dispositivo (BE #737)
    device_id: str | None = None

    def __post_init__(self):
        """Validación y configuración de severity"""
        super().__post_init__()
        if self.tokens_revoked_count < 0:
            raise ValueError("tokens_revoked_count no puede ser negativo")
        if not self.reason:
            raise ValueError("reason es requerido en RefreshTokenRevokedEvent")

        # Revocación por security breach es CRITICAL
        if self.reason == "security_breach":
            object.__setattr__(self, "severity", SecuritySeverity.CRITICAL)
        # Revocación por password change es HIGH
        elif self.reason == "password_change":
            object.__setattr__(self, "severity", SecuritySeverity.HIGH)
        # Revocación por logout normal es LOW
        else:
            object.__setattr__(self, "severity", SecuritySeverity.LOW)

    @property
    def is_failure(self) -> bool:
        """Solo la revocación por brecha es un fallo; logout, inactividad y cambio de contraseña son normales"""
        return self.reason == "security_breach"

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "tokens_revoked_count": self.tokens_revoked_count,
                "reason": self.reason,
                "device_id": self.device_id,
            }
        )
        return base


@dataclass(frozen=True)
class RefreshTokenReuseDetectedEvent(SecurityAuditEvent):
    """
    Robo de un refresh token detectado (F-02): llegó un token ya sustituido, fuera del
    margen de dos pestañas, cuyo sustituto ya se había usado. Dos sitios tienen la
    misma sesión; se revocan todos los tokens de ese dispositivo.

    Atributos:
        device_id: El dispositivo cuya sesión se cerró
        tokens_revoked_count: Cuántos tokens se revocaron (la cadena entera)
    """

    device_id: str = ""
    tokens_revoked_count: int = 0

    def __post_init__(self):
        """Validación y severidad: HIGH, va a Sentry con el tope de su tipo."""
        super().__post_init__()
        if self.tokens_revoked_count < 0:
            raise ValueError("tokens_revoked_count no puede ser negativo")
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    @property
    def is_failure(self) -> bool:
        """Es un fallo de seguridad: queda como rastro (WARNING)."""
        return True

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        return (
            f"REFRESH TOKEN REUSE | {user_info} | device {self.device_id} | "
            f"{self.tokens_revoked_count} revoked | IP: {self.ip_address}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa con el dispositivo y los revocados."""
        base = super().to_dict()
        base.update(
            {"device_id": self.device_id, "tokens_revoked_count": self.tokens_revoked_count}
        )
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
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "old_password_verified": self.old_password_verified,
            }
        )
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
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "email_verification_required": self.email_verification_required,
            }
        )
        return base


# ============================================================================
# ACCESS CONTROL EVENTS
# ============================================================================


@dataclass(frozen=True)
class AccountUnlockedAuditEvent(SecurityAuditEvent):
    """
    Un administrador desbloqueó a mano una cuenta bloqueada por fallos (hotfix 2.50.1).

    `user_id` es el administrador; `unlocked_user_id`, la cuenta desbloqueada.
    """

    unlocked_user_id: str = ""
    previous_failed_attempts: int = 0

    def __post_init__(self):
        """Validación y severidad: quitar un bloqueo de seguridad es HIGH."""
        super().__post_init__()
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        return (
            f"ACCOUNT UNLOCKED | {user_info} | Unlocked: {self.unlocked_user_id}"
            f" | Previous failures: {self.previous_failed_attempts}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa con los campos del desbloqueo."""
        base = super().to_dict()
        base.update(
            {
                "unlocked_user_id": self.unlocked_user_id,
                "previous_failed_attempts": self.previous_failed_attempts,
            }
        )
        return base


@dataclass(frozen=True)
class AccountDeactivatedAuditEvent(SecurityAuditEvent):
    """
    Un administrador desactivó una cuenta y cerró sus sesiones (BE #744).

    `user_id` es el administrador; `deactivated_user_id`, la cuenta.
    """

    deactivated_user_id: str = ""
    devices_revoked: int = 0
    tokens_revoked: int = 0

    def __post_init__(self):
        """Validación y severidad: dejar a alguien fuera de su cuenta es HIGH."""
        super().__post_init__()
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        return (
            f"ACCOUNT DEACTIVATED | {user_info} | Deactivated: {self.deactivated_user_id}"
            f" | Devices revoked: {self.devices_revoked} | Sessions revoked: {self.tokens_revoked}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa con los campos de la desactivación."""
        base = super().to_dict()
        base.update(
            {
                "deactivated_user_id": self.deactivated_user_id,
                "devices_revoked": self.devices_revoked,
                "tokens_revoked": self.tokens_revoked,
            }
        )
        return base


@dataclass(frozen=True)
class RefreshRejectedAuditEvent(SecurityAuditEvent):
    """
    Un refresco rechazado, con su motivo exacto (BE #733).

    Al cliente solo le llega SESSION_ENDED o SESSION_REJECTED: el motivo, que dice
    el estado de la cuenta, se queda aquí para investigar.
    """

    reason: str = ""
    rejected: bool = False

    def __post_init__(self):
        """Validación y severidad: un rechazo es MEDIUM; el final normal, LOW."""
        super().__post_init__()
        object.__setattr__(
            self, "severity", SecuritySeverity.MEDIUM if self.rejected else SecuritySeverity.LOW
        )

    @property
    def is_failure(self) -> bool:
        """Un rechazo cuenta como fallo (rastro en WARNING); el final normal, no."""
        return self.rejected

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        estado = "REJECTED" if self.rejected else "ENDED"
        return f"REFRESH {estado} | {user_info} | Reason: {self.reason} | IP: {self.ip_address}"

    def to_dict(self) -> dict[str, Any]:
        """Serializa con el motivo."""
        base = super().to_dict()
        base.update({"reason": self.reason, "rejected": self.rejected})
        return base


@dataclass(frozen=True)
class SecurityChangeFailedAuditEvent(SecurityAuditEvent):
    """
    Un cambio de /users/security rechazado, con su motivo (L1-L3, 7 nov 2026).

    Antes solo quedaba el cambio que salía bien: con una sesión robada se podían probar
    contraseñas sin rastro. Una contraseña actual equivocada es HIGH; lo demás (correo
    ocupado, contraseña repetida o débil, o cambiada entretanto), MEDIUM. Nunca lleva la
    contraseña ni el correo pedido.
    """

    reason: str = ""

    def __post_init__(self):
        """Severidad según el motivo."""
        super().__post_init__()
        alta = self.reason == "wrong_current_password"
        object.__setattr__(
            self, "severity", SecuritySeverity.HIGH if alta else SecuritySeverity.MEDIUM
        )

    @property
    def is_failure(self) -> bool:
        """Siempre un fallo: deja rastro en WARNING."""
        return True

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        return (
            f"SECURITY CHANGE FAILED | {user_info} | Reason: {self.reason} | IP: {self.ip_address}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa con el motivo."""
        base = super().to_dict()
        base.update({"reason": self.reason})
        return base


@dataclass(frozen=True)
class AccountReactivatedAuditEvent(SecurityAuditEvent):
    """
    Un administrador reactivó una cuenta (BE #744). Sus sesiones viejas no vuelven.

    `user_id` es el administrador; `reactivated_user_id`, la cuenta.
    """

    reactivated_user_id: str = ""
    tokens_revoked: int = 0

    def __post_init__(self):
        """Validación y severidad: devolver el acceso a una cuenta es HIGH."""
        super().__post_init__()
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        return (
            f"ACCOUNT REACTIVATED | {user_info} | Reactivated: {self.reactivated_user_id}"
            f" | Sessions revoked: {self.tokens_revoked}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa con los campos de la reactivación."""
        base = super().to_dict()
        base.update(
            {"reactivated_user_id": self.reactivated_user_id, "tokens_revoked": self.tokens_revoked}
        )
        return base


@dataclass(frozen=True)
class AdminRoleChangedAuditEvent(SecurityAuditEvent):
    """
    Un administrador dio o quitó el rol de administrador a una cuenta (F-20).

    `user_id` es el administrador; `target_user_id`, la cuenta; `is_admin`, el rol nuevo.
    """

    target_user_id: str = ""
    is_admin: bool = False

    def __post_init__(self):
        """Validación y severidad: cambiar quién administra es CRITICAL."""
        super().__post_init__()
        object.__setattr__(self, "severity", SecuritySeverity.CRITICAL)

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        accion = "GRANTED" if self.is_admin else "REVOKED"
        return f"ADMIN ROLE {accion} | {user_info} | Target: {self.target_user_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serializa con la cuenta y el rol nuevo."""
        base = super().to_dict()
        base.update({"target_user_id": self.target_user_id, "is_admin": self.is_admin})
        return base


@dataclass(frozen=True)
class AccountDeletedByAdminAuditEvent(SecurityAuditEvent):
    """
    Un administrador borró definitivamente una cuenta (F-20).

    `user_id` es el administrador; `deleted_user_id`, la cuenta borrada.
    """

    deleted_user_id: str = ""

    def __post_init__(self):
        """Validación y severidad: un borrado sin vuelta atrás es CRITICAL."""
        super().__post_init__()
        object.__setattr__(self, "severity", SecuritySeverity.CRITICAL)

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        return f"ACCOUNT DELETED BY ADMIN | {user_info} | Deleted: {self.deleted_user_id}"

    def to_dict(self) -> dict[str, Any]:
        """Serializa con la cuenta borrada."""
        base = super().to_dict()
        base.update({"deleted_user_id": self.deleted_user_id})
        return base


@dataclass(frozen=True)
class AdminEmailChangeRequestedAuditEvent(SecurityAuditEvent):
    """
    Un administrador pidió otro correo para una cuenta (F-20). Queda pendiente hasta
    que el usuario lo confirme (BE #753). Sin ninguno de los dos correos.

    `user_id` es el administrador; `target_user_id`, la cuenta.
    """

    target_user_id: str = ""

    def __post_init__(self):
        """Validación y severidad: el correo es la llave de la cuenta, CRITICAL."""
        super().__post_init__()
        object.__setattr__(self, "severity", SecuritySeverity.CRITICAL)

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        return (
            f"EMAIL CHANGE REQUESTED BY ADMIN | {user_info} | Target: {self.target_user_id}"
            " | pending confirmation"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa con la cuenta."""
        base = super().to_dict()
        base.update({"target_user_id": self.target_user_id})
        return base


@dataclass(frozen=True)
class UnverifiedAccountClaimedAuditEvent(SecurityAuditEvent):
    """Quien demostró el correo se quedó una cuenta sin verificar (pre-captura, #749).

    `via`: «google» (entró con un Google que lo verificó) o «password_reset» (usó el
    enlace de restablecer que llegó a su buzón).
    """

    via: str = "google"
    devices_revoked: int = 0
    tokens_revoked: int = 0
    google_unlinked: int = 0

    def __post_init__(self):
        """Validación y severidad: una cuenta que cambia de manos es HIGH."""
        super().__post_init__()
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        return (
            f"UNVERIFIED ACCOUNT CLAIMED VIA {self.via.upper()} | {user_info} | "
            f"devices revoked: {self.devices_revoked} | tokens revoked: {self.tokens_revoked} | "
            f"earlier Google unlinked: {self.google_unlinked}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa con lo que se cerró."""
        base = super().to_dict()
        base.update(
            {
                "via": self.via,
                "devices_revoked": self.devices_revoked,
                "tokens_revoked": self.tokens_revoked,
                "google_unlinked": self.google_unlinked,
            }
        )
        return base


@dataclass(frozen=True)
class GoogleAccountLinkedAuditEvent(SecurityAuditEvent):
    """Un Google quedó vinculado a una cuenta: da acceso a ella (revisión del registro)."""

    automatic: bool = False

    def __post_init__(self):
        """Validación y severidad: un acceso nuevo a la cuenta es HIGH."""
        super().__post_init__()
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        como = "automatically, by email" if self.automatic else "by the user"
        return f"GOOGLE LINKED | {user_info} | {como}"

    def to_dict(self) -> dict[str, Any]:
        """Serializa con cómo se vinculó."""
        base = super().to_dict()
        base.update({"automatic": self.automatic})
        return base


# Cómo se quitó un Google: desde el perfil o al restablecer la contraseña
GOOGLE_UNLINK_VIAS = frozenset({"profile", "password_reset"})


@dataclass(frozen=True)
class GoogleAccountUnlinkedAuditEvent(SecurityAuditEvent):
    """
    Un Google desvinculado: quita una forma de entrar, y con una sesión robada es el paso
    que deja fuera al dueño que entraba con Google. `via` dice cómo: desde el perfil
    («profile») o al restablecer la contraseña de una cuenta verificada
    («password_reset»). Los que se quitan al tomar una cuenta sin verificar van en
    `google_unlinked` de UnverifiedAccountClaimedAuditEvent, no aquí.
    """

    via: str = "profile"

    def __post_init__(self):
        """Validación y severidad: como un cambio de contraseña o de correo, HIGH."""
        super().__post_init__()
        # Solo los dos caminos conocidos: una errata se apuntaría como «by the user»
        if self.via not in GOOGLE_UNLINK_VIAS:
            raise ValueError(f"via must be one of {sorted(GOOGLE_UNLINK_VIAS)}")
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    def resumen(self, user_info: str) -> str:
        """La línea del log."""
        como = "on password reset" if self.via == "password_reset" else "by the user"
        return f"GOOGLE UNLINKED | {user_info} | {como}"

    def to_dict(self) -> dict[str, Any]:
        """Serializa con cómo se desvinculó."""
        base = super().to_dict()
        base.update({"via": self.via})
        return base


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
        object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    @property
    def is_failure(self) -> bool:
        """Un acceso denegado siempre es un fallo"""
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "resource_type": self.resource_type,
                "resource_id": self.resource_id,
                "action_attempted": self.action_attempted,
                "denial_reason": self.denial_reason,
            }
        )
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
        object.__setattr__(self, "severity", SecuritySeverity.MEDIUM)

    @property
    def is_failure(self) -> bool:
        """Superar el límite siempre es un fallo"""
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "endpoint": self.endpoint,
                "limit_type": self.limit_type,
                "limit_value": self.limit_value,
                "request_count": self.request_count,
            }
        )
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
        if not self.email or "@" not in self.email:
            raise ValueError("email debe ser válido")

        # Si falló, debe haber una razón (auditoría completa)
        if not self.success and not self.failure_reason:
            raise ValueError("failure_reason es requerido cuando success=False")

        # Severity:
        # - Fallido = HIGH (posible ataque de enumeración)
        # - Exitoso = MEDIUM (operación normal)
        if self.success:
            object.__setattr__(self, "severity", SecuritySeverity.MEDIUM)
        else:
            object.__setattr__(self, "severity", SecuritySeverity.HIGH)

    @property
    def is_failure(self) -> bool:
        """Fallo cuando no tuvo éxito"""
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "email": self.email,
                "success": self.success,
                "failure_reason": self.failure_reason,
            }
        )
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

        # Validar email. Un intento con un token que no es de nadie no tiene
        # usuario ni correo que poner: se audita igual (BE #519). Antes lanzaba
        # aquí, el intento no quedaba registrado y al usuario le llegaba
        # «email debe ser válido»
        # Un reseteo correcto siempre es de alguien, con su correo: la excepción
        # sin usuario vale solo para los fallidos (CodeRabbit, PR #524)
        if self.success and self.user_id is None:
            raise ValueError("user_id es requerido cuando success=True")
        if self.user_id is not None and (not self.email or "@" not in self.email):
            raise ValueError("email debe ser válido")

        # Si falló, debe haber una razón (auditoría completa)
        if not self.success and not self.failure_reason:
            raise ValueError("failure_reason es requerido cuando success=False")

        # Severity:
        # - Exitoso = HIGH (cambio de seguridad importante)
        # - Fallido = MEDIUM (intento fallido normal)
        if self.success:
            object.__setattr__(self, "severity", SecuritySeverity.HIGH)
        else:
            object.__setattr__(self, "severity", SecuritySeverity.MEDIUM)

    @property
    def is_failure(self) -> bool:
        """Fallo cuando no tuvo éxito"""
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Serializa con campos específicos del evento"""
        base = super().to_dict()
        base.update(
            {
                "email": self.email,
                "success": self.success,
                "failure_reason": self.failure_reason,
            }
        )
        return base
