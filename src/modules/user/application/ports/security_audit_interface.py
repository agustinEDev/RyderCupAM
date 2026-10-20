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
