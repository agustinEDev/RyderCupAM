"""
User Email Changed Event - Users Domain Layer

Evento de dominio que representa el cambio de email de un usuario.
Este evento se dispara cuando un usuario actualiza su dirección de correo electrónico.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class UserEmailChangedEvent(DomainEvent):
    """
    Evento que indica que un usuario ha cambiado su email.

    Este evento es crítico para:
    - Auditoría de cambios de seguridad
    - Enviar notificaciones a ambos emails
    - Actualizar integraciones externas
    - Revalidar email (si aplica)

    Attributes:
        user_id: ID del usuario que cambió su email
        old_email: Email anterior
        new_email: Nuevo email
        changed_at: Timestamp del cambio
    """

    # Datos del cambio (CAMPOS OBLIGATORIOS)
    user_id: str
    old_email: str
    new_email: str
    changed_at: datetime

    @property
    def aggregate_id(self) -> str:
        """El ID del agregado es el ID del usuario."""
        return self.user_id

    def to_dict(self) -> dict:
        """
        Serialización específica para UserEmailChangedEvent.

        Extiende la serialización base con campos específicos del evento.
        """
        base_dict = super().to_dict()
        base_dict.update(
            {
                "email_change": {
                    "old_email": self.old_email,
                    "new_email": self.new_email,
                    "changed_at": self.changed_at.isoformat(),
                }
            }
        )
        return base_dict

    def __str__(self) -> str:
        """Representación string legible del evento."""
        return f"UserEmailChangedEvent(user_id={self.user_id}, old={self.old_email}, new={self.new_email})"
