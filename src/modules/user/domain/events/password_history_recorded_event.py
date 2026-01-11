"""
Password History Recorded Event - Domain Layer

Evento de dominio emitido cuando se registra una nueva contraseña en el historial.
"""

from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


class PasswordHistoryRecordedEvent(DomainEvent):
    """
    Evento de dominio: Se registró una nueva contraseña en el historial.

    Este evento se emite cuando un usuario cambia su contraseña y se guarda
    el hash en el historial para prevenir reutilización.

    Security (OWASP A07):
        - Permite auditoría de cambios de contraseña
        - Facilita detección de patrones sospechosos
        - NO incluye el hash de la contraseña (solo para auditoría metadata)

    Attributes:
        user_id (str): UUID del usuario que cambió su contraseña
        history_id (str): UUID del registro de historial creado
        recorded_at (datetime): Timestamp del cambio
        total_history_count (int): Total de registros en historial después del cambio
    """

    def __init__(
        self,
        user_id: str,
        history_id: str,
        recorded_at: datetime,
        total_history_count: int,
    ):
        """
        Inicializa el evento de historial de contraseña.

        Args:
            user_id: UUID del usuario
            history_id: UUID del registro de historial
            recorded_at: Timestamp del cambio
            total_history_count: Total de registros en historial
        """
        super().__init__()
        self.user_id = user_id
        self.history_id = history_id
        self.recorded_at = recorded_at
        self.total_history_count = total_history_count

    def __repr__(self) -> str:
        """Representación para debugging."""
        return (
            f"PasswordHistoryRecordedEvent("
            f"user_id='{self.user_id}', "
            f"history_id='{self.history_id}', "
            f"recorded_at={self.recorded_at}, "
            f"total_history_count={self.total_history_count})"
        )
