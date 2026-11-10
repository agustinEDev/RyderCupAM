"""
Puerto del log de auditoría de seguridad para los casos de uso de usuario.

Los casos de uso no importan de infraestructura (contrato `layers` de
.importlinter): registran sus
eventos de auditoría por aquí, y el adaptador vive en
src/modules/user/infrastructure/security/security_audit_logger.py.
"""

from abc import ABC, abstractmethod


class ISecurityAuditLogger(ABC):
    """Lo que la capa de aplicación deja en el log de auditoría de seguridad."""

    @abstractmethod
    def log_device_revoked(
        self,
        user_id: str,
        device_id: str,
        ip_address: str,
        user_agent: str,
        tokens_revoked_count: int,
    ) -> None:
        """Deja constancia de que se revocó un dispositivo y cuántas sesiones cerró (BE #737)."""

    @abstractmethod
    def log_account_unlocked(
        self,
        user_id: str,
        unlocked_user_id: str,
        ip_address: str,
        user_agent: str,
        previous_failed_attempts: int,
    ) -> None:
        """Deja constancia de que un administrador desbloqueó una cuenta (hotfix 2.50.1).

        Args:
            user_id: ID del administrador
            unlocked_user_id: ID de la cuenta desbloqueada
            ip_address: IP del administrador ("unknown" si no se conoce)
            user_agent: Navegador ("unknown" si no se conoce)
            previous_failed_attempts: Fallos que llevaba la cuenta
        """

    @abstractmethod
    def log_account_deactivated(
        self,
        user_id: str,
        deactivated_user_id: str,
        devices_revoked: int,
        tokens_revoked: int,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Deja constancia de que un administrador desactivó una cuenta y cerró sus
        sesiones (BE #744).

        Args:
            user_id: ID del administrador
            deactivated_user_id: ID de la cuenta desactivada
            devices_revoked: Dispositivos revocados
            tokens_revoked: Sesiones (tokens de refresco) revocadas
            ip_address: IP del administrador ("unknown" si no se conoce)
            user_agent: Navegador del administrador ("unknown" si no se conoce)
        """

    @abstractmethod
    def log_account_reactivated(
        self,
        user_id: str,
        reactivated_user_id: str,
        tokens_revoked: int,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Deja constancia de que un administrador reactivó una cuenta (BE #744).

        Args:
            user_id: ID del administrador
            reactivated_user_id: ID de la cuenta reactivada
            tokens_revoked: Sesiones que se habían colado y se revocan al reactivarla
            ip_address: IP del administrador ("unknown" si no se conoce)
            user_agent: Navegador del administrador ("unknown" si no se conoce)
        """

    @abstractmethod
    def log_admin_role_changed(
        self,
        user_id: str,
        target_user_id: str,
        is_admin: bool,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Deja constancia de que un administrador dio o quitó el rol de admin (F-20).

        Args:
            user_id: ID del administrador
            target_user_id: ID de la cuenta
            is_admin: El rol nuevo
            ip_address: IP del administrador ("unknown" si no se conoce)
            user_agent: Navegador del administrador ("unknown" si no se conoce)
        """

    @abstractmethod
    def log_account_deleted_by_admin(
        self,
        user_id: str,
        deleted_user_id: str,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Deja constancia de que un administrador borró una cuenta (F-20).

        Args:
            user_id: ID del administrador
            deleted_user_id: ID de la cuenta borrada
            ip_address: IP del administrador ("unknown" si no se conoce)
            user_agent: Navegador del administrador ("unknown" si no se conoce)
        """

    @abstractmethod
    def log_admin_email_change_requested(
        self,
        user_id: str,
        target_user_id: str,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Deja constancia de que un administrador pidió otro correo para una cuenta (F-20).

        Sin ninguno de los dos correos.

        Args:
            user_id: ID del administrador
            target_user_id: ID de la cuenta
            ip_address: IP del administrador ("unknown" si no se conoce)
            user_agent: Navegador del administrador ("unknown" si no se conoce)
        """

    @abstractmethod
    def log_terms_accepted(
        self, user_id: str, ip_address: str, user_agent: str, terms_version: str
    ) -> None:
        """
        Deja constancia de que un usuario aceptó una versión de los Términos.

        Args:
            user_id: ID del usuario
            ip_address: IP del cliente ("unknown" si no se conoce)
            user_agent: Navegador ("unknown" si no se conoce)
            terms_version: La versión aceptada
        """

    # Los del log de seguridad que usaban los casos de uso importando la
    # infraestructura (#750): ahora por este puerto, inyectado
    @abstractmethod
    def log_login_attempt(
        self,
        user_id: str | None,
        email: str,
        success: bool,
        ip_address: str,
        user_agent: str,
        failure_reason: str | None = None,
    ) -> None:
        """Un intento de inicio de sesión, bueno o malo."""

    @abstractmethod
    def log_logout(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        refresh_tokens_revoked: int = 0,
    ) -> None:
        """Un cierre de sesión."""

    @abstractmethod
    def log_password_changed(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        old_password_verified: bool = True,
    ) -> None:
        """Una contraseña cambiada."""

    @abstractmethod
    def log_email_changed(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        email_verification_required: bool = True,
    ) -> None:
        """Un cambio de correo, pedido o confirmado."""

    @abstractmethod
    def log_security_change_failed(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        reason: str,
    ) -> None:
        """Un cambio de /users/security rechazado, con su motivo."""

    @abstractmethod
    def log_password_reset_requested(
        self,
        user_id: str | None,
        email: str,
        success: bool,
        ip_address: str,
        user_agent: str,
        failure_reason: str | None = None,
    ) -> None:
        """Una petición de restablecer la contraseña."""

    @abstractmethod
    def log_password_reset_completed(
        self,
        user_id: str | None,
        email: str,
        success: bool,
        ip_address: str,
        user_agent: str,
        failure_reason: str | None = None,
    ) -> None:
        """Un restablecimiento de contraseña, bueno o malo."""

    @abstractmethod
    def log_refresh_token_used(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        refresh_token_id: str,
        new_access_token_created: bool = True,
    ) -> None:
        """Un refresco de sesión que sale bien."""

    @abstractmethod
    def log_refresh_token_revoked(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        tokens_revoked_count: int,
        reason: str,
        device_id: str | None = None,
    ) -> None:
        """Sesiones revocadas, con su motivo."""

    @abstractmethod
    def log_refresh_token_reuse_detected(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        device_id: str,
        tokens_revoked_count: int,
    ) -> None:
        """Un refresh token sustituido reutilizado (robo, F-02): sesión del dispositivo cerrada."""

    @abstractmethod
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
        """Una cuenta sin verificar que se queda quien demuestra el correo."""

    @abstractmethod
    def log_google_account_linked(
        self,
        user_id: str,
        automatic: bool,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> None:
        """Un Google vinculado (automático o desde el perfil)."""

    @abstractmethod
    def log_google_account_unlinked(
        self,
        user_id: str,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
        via: str = "profile",
    ) -> None:
        """Un Google desvinculado: desde el perfil o al restablecer la contraseña."""
