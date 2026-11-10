"""
🔐 Security Logger - Servicio Especializado para Auditoría de Seguridad

Logger dedicado exclusivamente a eventos de seguridad con:
- Archivo separado (security_audit.log)
- Una línea JSON por evento en la salida estándar, que Render guarda: el fichero
  se pierde en cada despliegue (F-05b, auditoría OWASP del 9 nov 2026)
- Los HIGH y CRITICAL, también a Sentry, sin más dato personal que el id y la IP
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

import functools
import hashlib
import hmac
import logging
import logging.handlers
import queue
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import sentry_sdk

from src.config.settings import settings

from ...domain.events.security_events import (
    AccessDeniedEvent,
    AccountDeactivatedAuditEvent,
    AccountDeletedByAdminAuditEvent,
    AccountReactivatedAuditEvent,
    AccountUnlockedAuditEvent,
    AdminEmailChangeRequestedAuditEvent,
    AdminRoleChangedAuditEvent,
    EmailChangedEvent,
    GoogleAccountLinkedAuditEvent,
    GoogleAccountUnlinkedAuditEvent,
    LoginAttemptEvent,
    LogoutEvent,
    PasswordChangedEvent,
    PasswordResetRequestedAuditEvent,
    RateLimitExceededEvent,
    RefreshRejectedAuditEvent,
    RefreshTokenReuseDetectedEvent,
    RefreshTokenRevokedEvent,
    RefreshTokenUsedEvent,
    SecurityAuditEvent,
    SecurityChangeFailedAuditEvent,
    SecuritySeverity,
    TermsAcceptedEvent,
    UnverifiedAccountClaimedAuditEvent,
)
from .config import HandlerConfig, LogFormat, LogHandler, LogLevel
from .formatters import JsonFormatter, PythonLoggingFormatter

logger = logging.getLogger(__name__)

# Lo que llega a Sentry de cada evento: el id del usuario como único dato personal
# (F-05b). Ni el correo ni la IP, que se queda en el log (BE #466, revisión de la
# fase 2). El cuerpo de la petición lo quita el before_send (sentry_config.py)
_CAMPOS_PARA_SENTRY = frozenset({"event_id", "event_type", "occurred_on", "severity", "user_id"})
# La etiqueta con la que el before_send reconoce un evento de seguridad
ETIQUETA_DE_EVENTO_DE_SEGURIDAD = "security_event"
# Y la cuenta afectada por un administrador (`deactivated_user_id`...): otro id
_SUFIJO_DE_ID_DE_USUARIO = "_user_id"

_NIVEL_EN_SENTRY: dict[SecuritySeverity, Literal["warning", "error"]] = {
    SecuritySeverity.HIGH: "warning",
    SecuritySeverity.CRITICAL: "error",
}


# El hilo que escribe cada fichero de auditoría: uno por logger, para pararlo si el
# logger se vuelve a configurar (no quedan hilos huérfanos)
_ESCUCHAS: dict[str, logging.handlers.QueueListener] = {}
_CERROJO_DE_LAS_ESCUCHAS = threading.Lock()


def _para_la_escucha(nombre: str) -> None:
    """Para el hilo del logger `nombre`, si lo hay, escribiendo antes lo encolado."""
    with _CERROJO_DE_LAS_ESCUCHAS:
        anterior = _ESCUCHAS.pop(nombre, None)
    if anterior is not None:
        anterior.stop()
        for destino in anterior.handlers:
            destino.close()


class _SalidaEstandar(logging.StreamHandler):
    """Escribe en la salida estándar de CADA momento, no en la que había al crearse.

    El logger es un singleton: si guardara el `sys.stdout` del arranque, uno
    sustituido después (los tests lo cambian en cada uno) dejaría de recibir nada.
    """

    def __init__(self) -> None:
        """Arranca con la salida estándar actual."""
        super().__init__(sys.stdout)

    def emit(self, record: logging.LogRecord) -> None:
        """Escribe el registro en la salida estándar de ahora."""
        self.stream = sys.stdout
        super().emit(record)


def datos_para_sentry(event: SecurityAuditEvent) -> dict[str, Any]:
    """Los campos del evento que pueden ir a Sentry: ids, tipo, severidad y fecha."""
    return {
        clave: valor
        for clave, valor in event.to_dict().items()
        if clave in _CAMPOS_PARA_SENTRY or clave.endswith(_SUFIJO_DE_ID_DE_USUARIO)
    }


# La etiqueta separa esta clave de cualquier otro uso de SECRET_KEY (como la del CSRF)
_ETIQUETA_DE_LA_CLAVE_DEL_CORREO = b"rydercupfriends:security-log-email:v1"
_CIFRAS_DE_LA_HUELLA = 32  # 128 bits: de sobra para relacionar intentos


@functools.cache
def _clave_del_correo() -> bytes:
    """La clave del hash de los correos del log, derivada de SECRET_KEY con su etiqueta."""
    return hmac.new(
        settings.SECRET_KEY.encode(), _ETIQUETA_DE_LA_CLAVE_DEL_CORREO, hashlib.sha256
    ).digest()


def _normaliza(correo: str) -> str:
    """El correo sin espacios alrededor y en minúsculas."""
    return correo.strip().lower()


def enmascara_el_correo(correo: str) -> str:
    """`ana@gmail.com` -> `a***@gmail.com`; sin arroba, `***`; vacío, vacío."""
    normalizado = _normaliza(correo)
    if not normalizado:
        return ""
    local, arroba, dominio = normalizado.partition("@")
    if not arroba:
        return "***"
    return f"{local[:1]}***@{dominio}"


def huella_del_correo(correo: str) -> str:
    """HMAC-SHA256 del correo normalizado con la clave del log: relaciona sin guardarlo."""
    digest = hmac.new(_clave_del_correo(), _normaliza(correo).encode(), hashlib.sha256)
    return digest.hexdigest()[:_CIFRAS_DE_LA_HUELLA]


def _sin_el_correo(datos: dict[str, Any]) -> dict[str, Any]:
    """
    Los datos del evento con el correo tecleado enmascarado y su huella (revisión de la
    fase 2): ni el fichero ni stdout lo guardan en claro. La IP y el navegador se quedan.
    """
    correo = datos.get("email")
    if not isinstance(correo, str) or not correo:
        return datos
    return {**datos, "email": enmascara_el_correo(correo), "email_hash": huella_del_correo(correo)}


def solo_en_el_log(event: SecurityAuditEvent) -> bool:
    """
    Los eventos que no van a Sentry aunque sean HIGH (Agustín, 9 nov 2026): los
    logins fallidos y los restablecimientos pedidos para un correo que no es de nadie.
    Son los más frecuentes y no dicen nada que el log (stdout) no guarde ya.
    """
    if isinstance(event, LoginAttemptEvent):
        return not event.success
    return isinstance(event, PasswordResetRequestedAuditEvent) and event.user_id is None


class TopeDeSentry:
    """
    Como mucho un evento HIGH por tipo cada 10 minutos, por proceso (cupo de Sentry).

    El que sale dice cuántos de su tipo se omitieron desde el anterior. Los CRITICAL
    no pasan por aquí: van siempre.
    """

    VENTANA_S = 600

    def __init__(self, reloj: Callable[[], float] = time.monotonic) -> None:
        """
        Args:
            reloj: La hora en segundos; monotónica, para que un cambio de hora del
                sistema no abra ni cierre la ventana
        """
        self._reloj = reloj
        self._cerrojo = threading.Lock()
        self._ultimo: dict[str, float] = {}
        self._omitidos: dict[str, int] = {}

    def deja_pasar(self, tipo: str) -> int | None:
        """Los omitidos desde el último de ese tipo si este sale; None si no sale."""
        with self._cerrojo:
            ahora = self._reloj()
            ultimo = self._ultimo.get(tipo)
            if ultimo is not None and ahora - ultimo < self.VENTANA_S:
                self._omitidos[tipo] = self._omitidos.get(tipo, 0) + 1
                return None
            self._ultimo[tipo] = ahora
            return self._omitidos.pop(tipo, 0)


_TOPE = TopeDeSentry()


def avisa_a_sentry(event: SecurityAuditEvent) -> None:
    """Manda a Sentry un evento HIGH (warning) o CRITICAL (error); los demás, no.

    Uno por tipo de evento (fingerprint), con el id del usuario, nunca el correo ni
    la IP. Los HIGH, con tope (TopeDeSentry); los logins fallidos y los
    restablecimientos a un correo desconocido, nunca (solo_en_el_log). Si Sentry
    falla, solo se apunta el tipo del error: ni la petición ni el log de auditoría
    dependen de Sentry.
    """
    nivel = _NIVEL_EN_SENTRY.get(event.severity)
    if nivel is None or solo_en_el_log(event):
        return
    tipo = event.__class__.__name__
    omitidos = 0
    if event.severity is not SecuritySeverity.CRITICAL:
        pasa = _TOPE.deja_pasar(tipo)
        if pasa is None:
            return
        omitidos = pasa
    try:
        sentry_sdk.capture_message(
            f"Security event: {tipo}",
            level=nivel,
            fingerprint=["security-event", tipo],
            tags={ETIQUETA_DE_EVENTO_DE_SEGURIDAD: tipo, "security_severity": event.severity.value},
            contexts={
                "security_event": {**datos_para_sentry(event), "omitted_since_last": omitidos}
            },
            user={"id": event.user_id} if event.user_id else None,
        )
    except Exception as error:
        logger.warning("Security event not sent to Sentry: %s", type(error).__name__)


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

    @classmethod
    def _nombre_del_logger(cls, ruta: Path) -> str:
        """`security.audit` para el fichero de siempre; otro nombre para cualquier otro."""
        if ruta.resolve() == (cls.LOG_DIR / cls.LOG_FILE).resolve():
            return "security.audit"
        return f"security.audit.{hashlib.sha256(str(ruta.resolve()).encode()).hexdigest()[:12]}"

    def _setup_logger(self) -> logging.Logger:
        """
        Configura el logger de seguridad con handler rotativo y formato JSON.

        Returns:
            Logger configurado
        """
        # Un logger por fichero: si dos instancias compartieran uno, la segunda le
        # quitaría el handler a la primera (así se rompían los tests, BE #529)
        logger = logging.getLogger(self._nombre_del_logger(self.log_dir / self.log_file))
        logger.setLevel(logging.INFO)
        logger.propagate = False  # No propagar a root logger

        # Limpiar handlers existentes (por si se reinicializa), cerrando su fichero, y
        # parar el hilo que escribía para este logger
        for anterior in list(logger.handlers):
            anterior.close()
            logger.removeHandler(anterior)
        _para_la_escucha(logger.name)
        destinos: list[logging.Handler] = []

        log_path = self.log_dir / self.log_file

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

        # La misma línea JSON por la salida estándar: Render la guarda, y el
        # fichero se pierde en cada despliegue (F-05b). Va primero y no depende
        # del fichero: si este no se puede abrir, el log sigue aquí
        salida = _SalidaEstandar()
        salida.setLevel(logging.INFO)
        # Envolver JsonFormatter en PythonLoggingFormatter adapter para compatibilidad con logging.Handler
        salida.setFormatter(PythonLoggingFormatter(json_formatter))
        destinos.append(salida)

        try:
            # Crear directorio de logs si no existe, y el handler con rotación
            self.log_dir.mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                filename=str(log_path),
                maxBytes=self.MAX_BYTES,
                backupCount=self.BACKUP_COUNT,
                encoding="utf-8",
            )
        except OSError as error:
            # Sin fichero (en el Kind, uno de root que el usuario 10001 no abría): se
            # avisa y el log sigue por stdout (revisión de la fase 2)
            logging.getLogger(__name__).warning(
                "Security audit file unavailable (%s): logging to stdout only",
                type(error).__name__,
            )
        else:
            handler.setLevel(logging.INFO)
            handler.setFormatter(PythonLoggingFormatter(json_formatter))
            destinos.append(handler)

        # La petición solo encola; stdout y el fichero los escribe un hilo, en orden
        # (/code-review de la fase 2). `para` lo detiene al cerrar la app
        cola: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
        self._destinos = destinos
        self._encola = logging.handlers.QueueHandler(cola)
        self._escucha = logging.handlers.QueueListener(cola, *destinos, respect_handler_level=True)
        with _CERROJO_DE_LAS_ESCUCHAS:
            _ESCUCHAS[logger.name] = self._escucha
        self._escucha.start()
        logger.addHandler(self._encola)

        # Log inicial de arranque
        logger.info(
            "🔐 Security Logger iniciado",
            extra={
                "component": "SecurityLogger",
                "log_file": str(log_path),
                "max_size_mb": self.MAX_BYTES / (1024 * 1024),
                "backup_count": self.BACKUP_COUNT,
            },
        )

        return logger

    def vacia(self) -> None:
        """Espera a que el hilo haya escrito todo lo encolado (para leer el log al momento)."""
        if self._encola in self._logger.handlers:
            self._escucha.stop()
            self._escucha.start()

    def para(self) -> None:
        """
        Para el hilo al cerrar la app, escribiendo antes lo encolado. Lo que llegue
        después se escribe directamente: no se pierde nada.
        """
        if self._encola not in self._logger.handlers:
            return
        self._logger.removeHandler(self._encola)
        for destino in self._destinos:
            self._logger.addHandler(destino)
        self._escucha.stop()
        with _CERROJO_DE_LAS_ESCUCHAS:
            if _ESCUCHAS.get(self._logger.name) is self._escucha:
                del _ESCUCHAS[self._logger.name]

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
        # Serializar evento a dict, sin el correo tecleado en claro
        event_data = _sin_el_correo(event.to_dict())

        # Construir mensaje descriptivo
        message = self._build_message(event)

        # Nivel según el resultado y la severidad: un éxito no es un error (BE #229)
        log_level = self._log_level(event.severity, is_failure=event.is_failure)

        # Loggear con nivel apropiado
        self._logger.log(
            level=log_level,
            msg=message,
            extra={
                "security_event": event_data,
                "event_class": event.__class__.__name__,
                "severity": event.severity.value,
            },
        )

        # Tras escribirlo: lo que haga Sentry no quita el registro (F-05b)
        avisa_a_sentry(event)

    def _build_message(self, event: SecurityAuditEvent) -> str:  # noqa: PLR0911
        """
        Construye un mensaje descriptivo para el log.

        Args:
            event: Evento de seguridad

        Returns:
            Mensaje formateado
        """
        event_type = event.__class__.__name__
        user_info = f"User {event.user_id}" if event.user_id else "Anonymous"

        # Los eventos que saben resumirse (los de BE #732, #733 y #744)
        resumen = event.resumen(user_info)
        if resumen is not None:
            return resumen

        # Mensajes específicos por tipo de evento
        if isinstance(event, LoginAttemptEvent):
            status = "SUCCESS" if event.success else "FAILED"
            return (
                f"🔑 LOGIN {status} | {user_info} | Email: {enmascara_el_correo(event.email)}"
                f" | IP: {event.ip_address}"
            )

        if isinstance(event, LogoutEvent):
            return f"🚪 LOGOUT | {user_info} | Tokens revoked: {event.refresh_tokens_revoked}"

        if isinstance(event, PasswordChangedEvent):
            return f"🔐 PASSWORD CHANGED | {user_info} | Verified: {event.old_password_verified}"

        if isinstance(event, EmailChangedEvent):
            # Pedido (pendiente de confirmar desde la dirección nueva) o ya hecho (#749)
            if event.email_verification_required:
                return f"📧 EMAIL CHANGE REQUESTED | {user_info} | pending confirmation"
            return f"📧 EMAIL CHANGED | {user_info} | confirmed from the new address"

        if isinstance(event, AccessDeniedEvent):
            return f"⛔ ACCESS DENIED | {user_info} | Resource: {event.resource_type} | Action: {event.action_attempted}"

        if isinstance(event, RateLimitExceededEvent):
            return f"⚠️  RATE LIMIT EXCEEDED | {user_info} | Endpoint: {event.endpoint} | Limit: {event.limit_value}"

        if isinstance(event, TermsAcceptedEvent):
            return f"TERMS ACCEPTED | {user_info} | Version: {event.terms_version}"

        if isinstance(event, RefreshTokenUsedEvent):
            return f"🔄 REFRESH TOKEN USED | {user_info} | Token ID: {event.refresh_token_id}"

        if isinstance(event, RefreshTokenRevokedEvent):
            return f"🔒 REFRESH TOKENS REVOKED | {user_info} | Count: {event.tokens_revoked_count} | Reason: {event.reason}"

        # Fallback genérico
        return f"🔐 {event_type} | {user_info} | Severity: {event.severity.value}"

    @staticmethod
    def _log_level(severity: SecuritySeverity, *, is_failure: bool) -> int:
        """
        Nivel de logging de un evento de seguridad (BE #229).

        Sentry abre un issue con todo lo que llega a ERROR. La severidad sigue
        en el registro de auditoría tal cual; el nivel sale del resultado:
        - Éxito: INFO, sea cual sea la severidad.
        - Fallo: WARNING como mucho (rastro, no issue), salvo CRITICAL.

        Args:
            severity: Severidad de auditoría del evento
            is_failure: Si el evento cuenta que algo salió mal

        Returns:
            Nivel de logging (logging.INFO, logging.WARNING o logging.CRITICAL)
        """
        if not is_failure:
            return logging.INFO
        mapping = {
            SecuritySeverity.CRITICAL: logging.CRITICAL,  # 50
            SecuritySeverity.HIGH: logging.WARNING,  # 30
            SecuritySeverity.MEDIUM: logging.WARNING,  # 30
            SecuritySeverity.LOW: logging.INFO,  # 20
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

    def log_terms_accepted(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        terms_version: str,
    ) -> None:
        """
        Helper rápido para registrar la aceptación de los Términos.

        Args:
            user_id: ID del usuario
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            terms_version: La versión aceptada
        """
        event = TermsAcceptedEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            terms_version=terms_version,
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

    def log_security_change_failed(
        self, user_id: str, ip_address: str, user_agent: str, reason: str
    ) -> None:
        """Un cambio de /users/security rechazado, con su motivo (L1-L3)."""
        self.log_security_event(
            SecurityChangeFailedAuditEvent(
                user_id=user_id, ip_address=ip_address, user_agent=user_agent, reason=reason
            )
        )

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

    def log_refresh_rejected(
        self,
        ip_address: str,
        user_agent: str,
        reason: str,
        rejected: bool,
        user_id: str | None = None,
    ) -> None:
        """
        Helper rápido para registrar un refresco rechazado con su motivo (BE #733).

        Args:
            ip_address: IP del cliente
            user_agent: User-Agent del cliente
            reason: El motivo exacto (RefreshRejection)
            rejected: True si es un rechazo; False si es el final normal
            user_id: El usuario del token, si se conoce (para investigar)
        """
        self.log_security_event(
            RefreshRejectedAuditEvent(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                reason=reason,
                rejected=rejected,
            )
        )

    def log_account_deactivated(
        self,
        user_id: str,
        deactivated_user_id: str,
        devices_revoked: int,
        tokens_revoked: int,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> None:
        """
        Helper rápido para registrar la desactivación de una cuenta (BE #744).

        Args:
            user_id: ID del administrador
            deactivated_user_id: ID de la cuenta desactivada
            devices_revoked: Dispositivos revocados
            tokens_revoked: Sesiones revocadas
            ip_address: IP del administrador
            user_agent: User-Agent del administrador
        """
        self.log_security_event(
            AccountDeactivatedAuditEvent(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                deactivated_user_id=deactivated_user_id,
                devices_revoked=devices_revoked,
                tokens_revoked=tokens_revoked,
            )
        )

    def log_unverified_account_claimed(
        self,
        user_id: str,
        devices_revoked: int,
        tokens_revoked: int,
        google_unlinked: int = 0,
        via: str = "google",
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> None:
        """Helper rápido: se quedó una cuenta sin verificar quien demostró el correo."""
        self.log_security_event(
            UnverifiedAccountClaimedAuditEvent(
                user_id=user_id,
                via=via,
                ip_address=ip_address,
                user_agent=user_agent,
                devices_revoked=devices_revoked,
                tokens_revoked=tokens_revoked,
                google_unlinked=google_unlinked,
            )
        )

    def log_google_account_linked(
        self,
        user_id: str,
        automatic: bool,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> None:
        """Helper rápido: un Google vinculado a una cuenta (automático por correo o no)."""
        self.log_security_event(
            GoogleAccountLinkedAuditEvent(
                user_id=user_id, ip_address=ip_address, user_agent=user_agent, automatic=automatic
            )
        )

    def log_google_account_unlinked(
        self,
        user_id: str,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
        via: str = "profile",
    ) -> None:
        """Helper rápido: un Google desvinculado, desde el perfil o al restablecer."""
        self.log_security_event(
            GoogleAccountUnlinkedAuditEvent(
                user_id=user_id, ip_address=ip_address, user_agent=user_agent, via=via
            )
        )

    def log_account_reactivated(
        self,
        user_id: str,
        reactivated_user_id: str,
        tokens_revoked: int,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> None:
        """
        Helper rápido para registrar la reactivación de una cuenta (BE #744).

        Args:
            user_id: ID del administrador
            reactivated_user_id: ID de la cuenta reactivada
            tokens_revoked: Sesiones coladas que se revocan al reactivarla
            ip_address: IP del administrador
            user_agent: User-Agent del administrador
        """
        self.log_security_event(
            AccountReactivatedAuditEvent(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                reactivated_user_id=reactivated_user_id,
                tokens_revoked=tokens_revoked,
            )
        )

    def log_admin_role_changed(
        self,
        user_id: str,
        target_user_id: str,
        is_admin: bool,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> None:
        """Helper rápido: un administrador dio o quitó el rol de administrador (F-20)."""
        self.log_security_event(
            AdminRoleChangedAuditEvent(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                target_user_id=target_user_id,
                is_admin=is_admin,
            )
        )

    def log_account_deleted_by_admin(
        self,
        user_id: str,
        deleted_user_id: str,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> None:
        """Helper rápido: un administrador borró definitivamente una cuenta (F-20)."""
        self.log_security_event(
            AccountDeletedByAdminAuditEvent(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                deleted_user_id=deleted_user_id,
            )
        )

    def log_admin_email_change_requested(
        self,
        user_id: str,
        target_user_id: str,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> None:
        """Helper rápido: un administrador pidió otro correo para una cuenta (F-20)."""
        self.log_security_event(
            AdminEmailChangeRequestedAuditEvent(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                target_user_id=target_user_id,
            )
        )

    def log_account_unlocked(
        self,
        user_id: str,
        unlocked_user_id: str,
        ip_address: str,
        user_agent: str,
        previous_failed_attempts: int,
    ) -> None:
        """
        Helper rápido para registrar un desbloqueo manual de cuenta (hotfix 2.50.1).

        Args:
            user_id: ID del administrador que desbloquea
            unlocked_user_id: ID de la cuenta desbloqueada
            ip_address: IP del administrador
            user_agent: User-Agent del administrador
            previous_failed_attempts: Fallos que llevaba la cuenta
        """
        event = AccountUnlockedAuditEvent(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            unlocked_user_id=unlocked_user_id,
            previous_failed_attempts=previous_failed_attempts,
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
        device_id: str | None = None,
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
            device_id=device_id,
        )
        self.log_security_event(event)

    def log_refresh_token_reuse_detected(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        device_id: str,
        tokens_revoked_count: int,
    ) -> None:
        """
        Helper rápido: un refresh token sustituido reutilizado, un robo (F-02).

        Args:
            user_id: ID del usuario
            ip_address: IP de quien llegó con el token viejo
            user_agent: Su User-Agent
            device_id: El dispositivo cuya sesión se cerró
            tokens_revoked_count: Cuántos tokens se revocaron
        """
        self.log_security_event(
            RefreshTokenReuseDetectedEvent(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                device_id=device_id,
                tokens_revoked_count=tokens_revoked_count,
            )
        )

    def log_password_reset_requested(
        self,
        user_id: str | None,
        email: str,
        success: bool,
        ip_address: str,
        user_agent: str,
        failure_reason: str | None = None,
    ) -> None:
        """
        Helper rápido para registrar solicitud de reseteo de contraseña.

        Args:
            user_id: ID del usuario (None si email no existe)
            email: Email usado en la solicitud
            success: Si el email existe y se envió el enlace
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            failure_reason: Razón del fallo (requerido si success=False)

        Example:
            >>> security_logger.log_password_reset_requested(
            ...     user_id=None,
            ...     email="user@example.com",
            ...     success=False,
            ...     failure_reason="Email not found (not revealed to client)",
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
        """
        from src.shared.domain.events.security_events import (  # noqa: PLC0415
            PasswordResetRequestedAuditEvent,
        )

        event = PasswordResetRequestedAuditEvent(
            user_id=user_id,
            email=email,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.log_security_event(event)

    def log_password_reset_completed(
        self,
        user_id: str | None,
        email: str,
        success: bool,
        ip_address: str,
        user_agent: str,
        failure_reason: str | None = None,
    ) -> None:
        """
        Helper rápido para registrar reseteo de contraseña completado.

        Args:
            user_id: ID del usuario (None si token inválido)
            email: Email del usuario que reseteó la contraseña
            success: Si el reseteo fue exitoso
            ip_address: IP del cliente
            user_agent: User-Agent del navegador
            failure_reason: Razón del fallo (requerido si success=False)

        Example:
            >>> security_logger.log_password_reset_completed(
            ...     user_id="123",
            ...     email="user@example.com",
            ...     success=True,
            ...     failure_reason=None,
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
        """
        from src.shared.domain.events.security_events import (  # noqa: PLC0415
            PasswordResetCompletedAuditEvent,
        )

        event = PasswordResetCompletedAuditEvent(
            user_id=user_id,
            email=email,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
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
    global _security_logger_instance  # noqa: PLW0603 - Module-level singleton pattern
    if _security_logger_instance is None:
        _security_logger_instance = SecurityLogger()
    return _security_logger_instance
