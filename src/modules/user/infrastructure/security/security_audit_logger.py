"""Adaptador del puerto de auditoría: el SecurityLogger compartido (logs/security_audit.log)."""

from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.shared.infrastructure.logging.security_logger import get_security_logger


class SecurityAuditLogger(ISecurityAuditLogger):
    """Escribe en el log de auditoría de seguridad de la aplicación."""

    def log_terms_accepted(
        self, user_id: str, ip_address: str, user_agent: str, terms_version: str
    ) -> None:
        get_security_logger().log_terms_accepted(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            terms_version=terms_version,
        )
