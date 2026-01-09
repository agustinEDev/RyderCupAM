"""
Email Verified Event - Users Domain Layer

Evento de dominio que representa la verificación exitosa del email de un usuario.
Este evento se dispara cuando un usuario confirma su dirección de correo electrónico.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class EmailVerifiedEvent(DomainEvent):
    """
    Evento que indica que un usuario ha verificado su email.

    Este evento contiene información sobre la verificación del email
    y puede ser usado por otros bounded contexts para realizar acciones como:
    - Enviar email de bienvenida post-verificación
    - Activar funcionalidades completas
    - Registrar analytics
    - Notificar a administradores

    Attributes:
        user_id: ID del usuario que verificó su email
        email: Email que fue verificado
        verified_at: Timestamp de cuándo se verificó
    """

    user_id: str
    email: str
    verified_at: datetime

    @property
    def aggregate_id(self) -> str:
        """El ID del agregado es el ID del usuario."""
        return self.user_id

    def to_dict(self) -> dict:
        """
        Serialización específica para EmailVerifiedEvent.

        Extiende la serialización base con campos específicos del evento.
        Asegura que verified_at se serialice correctamente en formato ISO.
        """
        base_dict = super().to_dict()
        # Actualizar el diccionario 'data' para que todo sea JSON-serializable
        data = base_dict.get("data", {})
        data.update(
            {
                "user_id": self.user_id,
                "email": self.email,
                "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            }
        )
        base_dict["data"] = data
        return base_dict

    def __str__(self) -> str:
        """Representación string legible del evento."""
        return f"EmailVerifiedEvent(user_id={self.user_id}, email={self.email}, id={self.event_id[:8]}...)"
