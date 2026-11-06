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

    def log_terms_accepted(
        self, user_id: str, ip_address: str, user_agent: str, terms_version: str
    ) -> None:
        get_security_logger().log_terms_accepted(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            terms_version=terms_version,
        )
