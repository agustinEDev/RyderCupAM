"""
🔐 Security Logger - Servicio Especializado para Auditoría de Seguridad

Logger dedicado exclusivamente a eventos de seguridad con:
- Archivo separado (security_audit.log)
- Formateo JSON estructurado
- Rotación automática de logs
- Contexto enriquecido (IP, User-Agent, correlation ID)
- Cumplimiento OWASP A09 (Security Logging and Monitoring)

Características:
- Thread-safe
- Async-friendly
- Integración con Domain Events
- Helpers para eventos comunes
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Any

from ...domain.events.security_events import (
    AccessDeniedEvent,
    EmailChangedEvent,
    LoginAttemptEvent,
    LogoutEvent,
    PasswordChangedEvent,
    RateLimitExceededEvent,
    RefreshTokenRevokedEvent,
    RefreshTokenUsedEvent,
    SecurityAuditEvent,
    SecuritySeverity,
)
from .config import HandlerConfig, LogConfig, LogFormat, LogHandler, LogLevel
from .formatters import JsonFormatter, PythonLoggingFormatter


class SecurityLogger:
    """
    Logger especializado para eventos de seguridad.

    Mantiene un log separado de auditoría con toda la información
    necesaria para compliance, forensics y detección de amenazas.

    Características:
    - Archivo dedicado: logs/security_audit.log
    - Rotación automática (10MB, 5 backups)
    - Formato JSON para análisis
    - Severity levels de seguridad
    - Contexto completo de requests

    Ejemplo:
        security_logger = SecurityLogger()

        # Opción 1: Log de evento completo
        event = LoginAttemptEvent(
            user_id="123",
            email="user@example.com",
            success=True,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
        )
        security_logger.log_security_event(event)

        # Opción 2: Helper rápido
        security_logger.log_login_attempt(
            user_id="123",
            email="user@example.com",
            success=False,
            failure_reason="Invalid credentials",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
        )
    """

    # Configuración de archivo de logs
    LOG_DIR = Path("logs")
    LOG_FILE = "security_audit.log"
    MAX_BYTES = 10 * 1024 * 1024  # 10MB
    BACKUP_COUNT = 5

    def __init__(
        self,
        log_dir: Path | None = None,
        log_file: str | None = None,
    ):
        """
        Inicializa el SecurityLogger.

        Args:
            log_dir: Directorio de logs (default: logs/)
            log_file: Nombre del archivo (default: security_audit.log)
        """
        self.log_dir = log_dir or self.LOG_DIR
        self.log_file = log_file or self.LOG_FILE
        self._logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """
        Configura el logger de seguridad con handler rotativo y formato JSON.

        Returns:
            Logger configurado
        """
        # Crear logger único para seguridad
        logger = logging.getLogger("security.audit")
        logger.setLevel(logging.INFO)
        logger.propagate = False  # No propagar a root logger

        # Limpiar handlers existentes (por si se reinicializa)
        logger.handlers.clear()

        # Crear directorio de logs si no existe
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Handler con rotación automática
        log_path = self.log_dir / self.log_file
        handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),
            maxBytes=self.MAX_BYTES,
            backupCount=self.BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setLevel(logging.INFO)

        # Formatter JSON para logs estructurados
        handler_config = HandlerConfig(
            type=LogHandler.ROTATING_FILE,
            level=LogLevel.INFO,
            format=LogFormat.JSON,
            filename=str(log_path),
            max_bytes=self.MAX_BYTES,
            backup_count=self.BACKUP_COUNT,
            date_format="%Y-%m-%d %H:%M:%S",
            include_correlation_id=True,
            include_context=True,
        )
        json_formatter = JsonFormatter(config=handler_config)
        # Envolver JsonFormatter en PythonLoggingFormatter adapter para compatibilidad con logging.Handler
        handler.setFormatter(PythonLoggingFormatter(json_formatter))

        logger.addHandler(handler)

        # Log inicial de arranque
        logger.info(
            "🔐 Security Logger iniciado",
            extra={
                "component": "SecurityLogger",
                "log_file": str(log_path),
                "max_size_mb": self.MAX_BYTES / (1024 * 1024),
                "backup_count": self.BACKUP_COUNT,
            }
        )

        return logger

    def log_security_event(self, event: SecurityAuditEvent) -> None:
        """
        Registra un evento de seguridad completo en el audit log.

        Args:
            event: Evento de seguridad a registrar

        Example:
            event = LoginAttemptEvent(
                user_id="123",
                email="user@example.com",
                success=False,
                failure_reason="Invalid credentials",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0...",
            )
            security_logger.log_security_event(event)
        """
        # Serializar evento a dict
        event_data = event.to_dict()

        # Construir mensaje descriptivo
        message = self._build_message(event)

        # Determinar nivel de logging según severity
        log_level = self._severity_to_log_level(event.severity)

        # Loggear con nivel apropiado
        self._logger.log(
            level=log_level,
            msg=message,
            extra={
                "security_event": event_data,
                "event_class": event.__class__.__name__,
                "severity": event.severity.value,
            }
        )

    def _build_message(self, event: SecurityAuditEvent) -> str:
        """
        Construye un mensaje descriptivo para el log.

        Args:
            event: Evento de seguridad

        Returns:
            Mensaje formateado
        """
        event_type = event.__class__.__name__
        user_info = f"User {event.user_id}" if event.user_id else "Anonymous"

        # Mensajes específicos por tipo de evento
        if isinstance(event, LoginAttemptEvent):
            status = "SUCCESS" if event.success else "FAILED"
            return f"🔑 LOGIN {status} | {user_info} | Email: {event.email} | IP: {event.ip_address}"

        elif isinstance(event, LogoutEvent):
            return f"🚪 LOGOUT | {user_info} | Tokens revoked: {event.refresh_tokens_revoked}"

        elif isinstance(event, PasswordChangedEvent):
            return f"🔐 PASSWORD CHANGED | {user_info} | Verified: {event.old_password_verified}"

        elif isinstance(event, EmailChangedEvent):
            return f"📧 EMAIL CHANGED | {user_info} | Verification required: {event.email_verification_required}"

        elif isinstance(event, AccessDeniedEvent):
            return f"⛔ ACCESS DENIED | {user_info} | Resource: {event.resource_type} | Action: {event.action_attempted}"

        elif isinstance(event, RateLimitExceededEvent):
            return f"⚠️  RATE LIMIT EXCEEDED | {user_info} | Endpoint: {event.endpoint} | Limit: {event.limit_value}"

        elif isinstance(event, RefreshTokenUsedEvent):
            return f"🔄 REFRESH TOKEN USED | {user_info} | Token ID: {event.refresh_token_id}"

        elif isinstance(event, RefreshTokenRevokedEvent):
            return f"🔒 REFRESH TOKENS REVOKED | {user_info} | Count: {event.tokens_revoked_count} | Reason: {event.reason}"

        else:
            # Fallback genérico
            return f"🔐 {event_type} | {user_info} | Severity: {event.severity.value}"

    def _severity_to_log_level(self, severity: SecuritySeverity) -> int:
        """
        Convierte severity de seguridad a nivel de logging de Python.

        Args:
            severity: Nivel de severidad del evento

        Returns:
            Nivel de logging (logging.INFO, logging.WARNING, etc.)
        """
        mapping = {
            SecuritySeverity.CRITICAL: logging.CRITICAL,  # 50
            SecuritySeverity.HIGH: logging.ERROR,         # 40
            SecuritySeverity.MEDIUM: logging.WARNING,     # 30
            SecuritySeverity.LOW: logging.INFO,           # 20
        }
        return mapping.get(severity, logging.INFO)

    # ========================================================================
    # HELPER METHODS - Shortcuts para eventos comunes
    # ========================================================================

    def log_login_attempt(
        self,
        user_id: str | None,
        email: str,
        success: bool,
        ip_address: str,
        user_agent: str,
        failure_reason: str | None = None,
    ) -> None:
        """
        Helper rápido para registrar intento de login.

        Args:
            user_id: ID del usuario (None si login falló)
            email: Email usado en el intento
            success: Si el login fue exitoso
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            failure_reason: Razón del fallo (requerido si success=False)
        """
        event = LoginAttemptEvent(
            user_id=user_id,
            email=email,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.log_security_event(event)

    def log_logout(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        refresh_tokens_revoked: int = 0,
    ) -> None:
        """
        Helper rápido para registrar logout.

        Args:
            user_id: ID del usuario
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            refresh_tokens_revoked: Cantidad de tokens revocados
        """
        event = LogoutEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            refresh_tokens_revoked=refresh_tokens_revoked,
        )
        self.log_security_event(event)

    def log_password_changed(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        old_password_verified: bool = True,
    ) -> None:
        """
        Helper rápido para registrar cambio de contraseña.

        Args:
            user_id: ID del usuario
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            old_password_verified: Si se verificó la contraseña anterior
        """
        event = PasswordChangedEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            old_password_verified=old_password_verified,
        )
        self.log_security_event(event)

    def log_email_changed(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        email_verification_required: bool = True,
    ) -> None:
        """
        Helper rápido para registrar cambio de email.

        Args:
            user_id: ID del usuario
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            email_verification_required: Si requiere verificación
        """
        event = EmailChangedEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            email_verification_required=email_verification_required,
        )
        self.log_security_event(event)

    def log_access_denied(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        resource_type: str,
        resource_id: str | None,
        action_attempted: str,
        denial_reason: str,
    ) -> None:
        """
        Helper rápido para registrar acceso denegado.

        Args:
            user_id: ID del usuario
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            resource_type: Tipo de recurso ("competition", "enrollment")
            resource_id: ID del recurso
            action_attempted: Acción intentada ("update", "delete")
            denial_reason: Razón del rechazo ("not_creator", "not_enrolled")
        """
        event = AccessDeniedEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action_attempted=action_attempted,
            denial_reason=denial_reason,
        )
        self.log_security_event(event)

    def log_rate_limit_exceeded(
        self,
        user_id: str | None,
        ip_address: str,
        user_agent: str,
        endpoint: str,
        limit_type: str,
        limit_value: str,
        request_count: int,
    ) -> None:
        """
        Helper rápido para registrar rate limiting.

        Args:
            user_id: ID del usuario (None si no autenticado)
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            endpoint: Endpoint que alcanzó el límite
            limit_type: Tipo de límite ("per_minute", "per_hour")
            limit_value: Valor del límite ("5/minute")
            request_count: Número de requests realizados
        """
        event = RateLimitExceededEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            endpoint=endpoint,
            limit_type=limit_type,
            limit_value=limit_value,
            request_count=request_count,
        )
        self.log_security_event(event)

    def log_refresh_token_used(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        refresh_token_id: str,
        new_access_token_created: bool = True,
    ) -> None:
        """
        Helper rápido para registrar uso de refresh token.

        Args:
            user_id: ID del usuario
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            refresh_token_id: ID del refresh token usado
            new_access_token_created: Si se creó un nuevo access token
        """
        event = RefreshTokenUsedEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            refresh_token_id=refresh_token_id,
            new_access_token_created=new_access_token_created,
        )
        self.log_security_event(event)

    def log_refresh_token_revoked(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        tokens_revoked_count: int,
        reason: str,
    ) -> None:
        """
        Helper rápido para registrar revocación de refresh tokens.

        Args:
            user_id: ID del usuario
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            tokens_revoked_count: Cantidad de tokens revocados
            reason: Razón ("logout", "password_change", "security_breach")
        """
        event = RefreshTokenRevokedEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            tokens_revoked_count=tokens_revoked_count,
            reason=reason,
        )
        self.log_security_event(event)


# Singleton global para fácil acceso
_security_logger_instance: SecurityLogger | None = None


def get_security_logger() -> SecurityLogger:
    """
    Obtiene la instancia singleton del SecurityLogger.

    Returns:
        SecurityLogger configurado
    """
    global _security_logger_instance
    if _security_logger_instance is None:
        _security_logger_instance = SecurityLogger()
    return _security_logger_instance
