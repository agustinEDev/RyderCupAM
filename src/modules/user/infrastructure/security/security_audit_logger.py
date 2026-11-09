"""Adaptador del puerto de auditoría: el SecurityLogger compartido (logs/security_audit.log)."""

from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.shared.infrastructure.logging.security_logger import get_security_logger


class SecurityAuditLogger(ISecurityAuditLogger):
    """Escribe en el log de auditoría de seguridad de la aplicación."""

    def log_device_revoked(
        self,
        user_id: str,
        device_id: str,
        ip_address: str,
        user_agent: str,
        tokens_revoked_count: int,
    ) -> None:
        get_security_logger().log_refresh_token_revoked(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            tokens_revoked_count=tokens_revoked_count,
            reason="device_revoked",
            device_id=device_id,
        )

    def log_account_unlocked(
        self,
        user_id: str,
        unlocked_user_id: str,
        ip_address: str,
        user_agent: str,
        previous_failed_attempts: int,
    ) -> None:
        get_security_logger().log_account_unlocked(
            user_id=user_id,
            unlocked_user_id=unlocked_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            previous_failed_attempts=previous_failed_attempts,
        )

    def log_account_deactivated(
        self,
        user_id: str,
        deactivated_user_id: str,
        devices_revoked: int,
        tokens_revoked: int,
        ip_address: str,
        user_agent: str,
    ) -> None:
        get_security_logger().log_account_deactivated(
            user_id=user_id,
            deactivated_user_id=deactivated_user_id,
            devices_revoked=devices_revoked,
            tokens_revoked=tokens_revoked,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_account_reactivated(
        self,
        user_id: str,
        reactivated_user_id: str,
        tokens_revoked: int,
        ip_address: str,
        user_agent: str,
    ) -> None:
        get_security_logger().log_account_reactivated(
            user_id=user_id,
            reactivated_user_id=reactivated_user_id,
            tokens_revoked=tokens_revoked,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_admin_role_changed(
        self,
        user_id: str,
        target_user_id: str,
        is_admin: bool,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Un administrador dio o quitó el rol de administrador (F-20)."""
        get_security_logger().log_admin_role_changed(
            user_id=user_id,
            target_user_id=target_user_id,
            is_admin=is_admin,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_account_deleted_by_admin(
        self,
        user_id: str,
        deleted_user_id: str,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Un administrador borró una cuenta (F-20)."""
        get_security_logger().log_account_deleted_by_admin(
            user_id=user_id,
            deleted_user_id=deleted_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_admin_email_change_requested(
        self,
        user_id: str,
        target_user_id: str,
        ip_address: str,
        user_agent: str,
    ) -> None:
        """Un administrador pidió otro correo para una cuenta (F-20)."""
        get_security_logger().log_admin_email_change_requested(
            user_id=user_id,
            target_user_id=target_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_terms_accepted(
        self, user_id: str, ip_address: str, user_agent: str, terms_version: str
    ) -> None:
        get_security_logger().log_terms_accepted(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            terms_version=terms_version,
        )

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
        get_security_logger().log_login_attempt(
            user_id=user_id,
            email=email,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
        )

    def log_logout(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        refresh_tokens_revoked: int = 0,
    ) -> None:
        """Un cierre de sesión."""
        get_security_logger().log_logout(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            refresh_tokens_revoked=refresh_tokens_revoked,
        )

    def log_password_changed(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        old_password_verified: bool = True,
    ) -> None:
        """Una contraseña cambiada."""
        get_security_logger().log_password_changed(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            old_password_verified=old_password_verified,
        )

    def log_email_changed(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        email_verification_required: bool = True,
    ) -> None:
        """Un cambio de correo, pedido o confirmado."""
        get_security_logger().log_email_changed(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            email_verification_required=email_verification_required,
        )

    def log_security_change_failed(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        reason: str,
    ) -> None:
        """Un cambio de /users/security rechazado, con su motivo."""
        get_security_logger().log_security_change_failed(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason,
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
        """Una petición de restablecer la contraseña."""
        get_security_logger().log_password_reset_requested(
            user_id=user_id,
            email=email,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
        )

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
        get_security_logger().log_password_reset_completed(
            user_id=user_id,
            email=email,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
        )

    def log_refresh_token_used(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        refresh_token_id: str,
        new_access_token_created: bool = True,
    ) -> None:
        """Un refresco de sesión que sale bien."""
        get_security_logger().log_refresh_token_used(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            refresh_token_id=refresh_token_id,
            new_access_token_created=new_access_token_created,
        )

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
        get_security_logger().log_refresh_token_revoked(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            tokens_revoked_count=tokens_revoked_count,
            reason=reason,
            device_id=device_id,
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
        """Una cuenta sin verificar que se queda quien demuestra el correo."""
        get_security_logger().log_unverified_account_claimed(
            user_id=user_id,
            devices_revoked=devices_revoked,
            tokens_revoked=tokens_revoked,
            google_unlinked=google_unlinked,
            via=via,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_google_account_linked(
        self,
        user_id: str,
        automatic: bool,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
    ) -> None:
        """Un Google vinculado (automático o desde el perfil)."""
        get_security_logger().log_google_account_linked(
            user_id=user_id,
            automatic=automatic,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def log_google_account_unlinked(
        self,
        user_id: str,
        ip_address: str = "unknown",
        user_agent: str = "unknown",
        via: str = "profile",
    ) -> None:
        """Un Google desvinculado: desde el perfil o al restablecer la contraseña."""
        get_security_logger().log_google_account_unlinked(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            via=via,
        )
