"""
Puerto del log de auditoría de seguridad para los casos de uso de usuario.

Los casos de uso no importan de infraestructura (CLAUDE.md): registran sus
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
        self, user_id: str, deactivated_user_id: str, devices_revoked: int, tokens_revoked: int
    ) -> None:
        """Deja constancia de que un administrador desactivó una cuenta y cerró sus
        sesiones (BE #744).

        Args:
            user_id: ID del administrador
            deactivated_user_id: ID de la cuenta desactivada
            devices_revoked: Dispositivos revocados
            tokens_revoked: Sesiones (tokens de refresco) revocadas
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
