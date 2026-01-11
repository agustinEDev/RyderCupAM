"""
User Password Changed Event - Users Domain Layer

Evento de dominio que representa el cambio de contraseña de un usuario.
Este evento se dispara cuando un usuario actualiza su password.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class UserPasswordChangedEvent(DomainEvent):
    """
    Evento que indica que un usuario ha cambiado su password.

    Este evento es crítico para:
    - Auditoría de seguridad
    - Enviar notificaciones al usuario
    - Invalidar sesiones existentes (si aplica)
    - Alertas de seguridad

    NOTA: Por seguridad, NO almacenamos el password anterior ni el nuevo,
    solo registramos que ocurrió el cambio.

    Attributes:
        user_id: ID del usuario que cambió su password
        changed_at: Timestamp del cambio
        changed_from_ip: IP desde donde se realizó el cambio (opcional)
    """

    # Datos del cambio (CAMPOS OBLIGATORIOS)
    user_id: str
    changed_at: datetime

    # Metadatos de seguridad (OPCIONAL)
    changed_from_ip: str | None = None

    @property
    def aggregate_id(self) -> str:
        """El ID del agregado es el ID del usuario."""
        return self.user_id

    def to_dict(self) -> dict:
        """
        Serialización específica para UserPasswordChangedEvent.

        Extiende la serialización base con campos específicos del evento.
        """
        base_dict = super().to_dict()
        base_dict.update(
            {
                "password_change": {
                    "changed_at": self.changed_at.isoformat(),
                    "changed_from_ip": self.changed_from_ip,
                }
            }
        )
        return base_dict

    def __str__(self) -> str:
        """Representación string legible del evento."""
        ip_info = f", ip={self.changed_from_ip}" if self.changed_from_ip else ""
        return f"UserPasswordChangedEvent(user_id={self.user_id}{ip_info})"
