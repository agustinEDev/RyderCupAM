"""
Handicap Updated Event - Users Domain Layer

Evento de dominio que representa la actualización del hándicap de un usuario.
Este evento se dispara cuando el hándicap de un usuario es actualizado.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class HandicapUpdatedEvent(DomainEvent):
    """
    Evento que indica que el hándicap de un usuario ha sido actualizado.

    Este evento contiene la información del cambio de hándicap
    y puede ser usado para:
    - Auditoría de cambios
    - Notificar a otros sistemas
    - Actualizar estadísticas
    - Recalcular handicaps de equipos

    Attributes:
        user_id: ID del usuario cuyo hándicap fue actualizado
        old_handicap: Hándicap anterior (None si no tenía)
        new_handicap: Nuevo hándicap (None si fue eliminado)
        updated_at: Timestamp de la actualización
    """

    # Datos del cambio de hándicap
    user_id: str
    old_handicap: float | None
    new_handicap: float | None
    updated_at: datetime

    @property
    def aggregate_id(self) -> str:
        """El ID del agregado es el ID del usuario."""
        return self.user_id

    @property
    def has_changed(self) -> bool:
        """Verifica si el hándicap realmente cambió."""
        return self.old_handicap != self.new_handicap

    @property
    def handicap_delta(self) -> float | None:
        """
        Calcula la diferencia entre el hándicap nuevo y el viejo.

        Returns:
            La diferencia (nuevo - viejo) o None si alguno es None
        """
        if self.old_handicap is None or self.new_handicap is None:
            return None
        return self.new_handicap - self.old_handicap

    def to_dict(self) -> dict:
        """
        Serialización específica para HandicapUpdatedEvent.

        Extiende la serialización base con campos específicos del evento.
        """
        base_dict = super().to_dict()
        base_dict.update({
            'handicap_change': {
                'user_id': self.user_id,
                'old_value': self.old_handicap,
                'new_value': self.new_handicap,
                'delta': self.handicap_delta,
                'updated_at': self.updated_at.isoformat(),
            }
        })
        return base_dict

    def __str__(self) -> str:
        """Representación string legible del evento."""
        return (
            f"HandicapUpdatedEvent(user_id={self.user_id}, "
            f"{self.old_handicap} -> {self.new_handicap}, "
            f"event_id={self.event_id[:8]}...)"
        )
