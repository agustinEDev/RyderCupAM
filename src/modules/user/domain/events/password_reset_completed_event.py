from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


class PasswordResetCompletedEvent(DomainEvent):
    """
    Evento de dominio que se emite cuando un usuario completa exitosamente el reseteo de su contraseña.

    Este evento se genera DESPUÉS de que:
    1. El token de reseteo se validó correctamente
    2. La nueva contraseña cumple con la política de seguridad (OWASP ASVS V2.1)
    3. El password hash se actualizó en la base de datos
    4. Todas las sesiones activas se invalidaron (logout forzado)

    Attributes:
        user_id: ID del usuario que completó el reseteo
        email: Email del usuario (para envío de confirmación)
        completed_at: Timestamp de cuándo se completó el reseteo
        ip_address: Dirección IP desde donde se hizo el reseteo (para auditoría)
        user_agent: User agent del navegador (para detección de anomalías)

    Security:
        - Trigger para invalidar TODOS los refresh tokens del usuario
        - Trigger para enviar email de notificación "Tu contraseña fue cambiada"
        - Se registra en el SecurityLogger con severity HIGH
        - Permite detectar cambios de contraseña no autorizados

    Nota:
        Este evento es similar a UserPasswordChangedEvent pero específico para el flujo
        de recuperación (incluye más contexto de seguridad).
    """

    def __init__(
        self,
        user_id: str,
        email: str,
        completed_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None
    ):
        super().__init__()
        self.user_id = user_id
        self.email = email
        self.completed_at = completed_at
        self.ip_address = ip_address
        self.user_agent = user_agent

    def __repr__(self) -> str:
        return (
            f"PasswordResetCompletedEvent(user_id={self.user_id}, "
            f"email={self.email}, completed_at={self.completed_at})"
        )
