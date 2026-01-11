"""
User Logged Out Event - Users Domain Layer

Evento de dominio que representa el cierre de sesión exitoso de un usuario.
Este evento se dispara cuando un usuario hace logout del sistema.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class UserLoggedOutEvent(DomainEvent):
    """
    Evento que indica que un usuario ha cerrado sesión en el sistema.

    Este evento contiene información relevante del logout y puede ser usado
    por otros bounded contexts para realizar acciones como:
    - Auditoría de seguridad
    - Analytics de sesiones
    - Invalidación de caché
    - Notificaciones de seguridad

    Attributes:
        user_id: ID específico del usuario (se usa como aggregate_id automáticamente)
        logged_out_at: Timestamp exacto del logout
        token_used: Token JWT que se utilizó (opcional, para blacklist futura)
        ip_address: Dirección IP desde donde se hizo logout (opcional)
        user_agent: User agent del browser/app (opcional)
    """

    user_id: str
    logged_out_at: datetime
    token_used: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    def __post_init__(self):
        """
        Post-inicialización que llama al __post_init__ de la clase base
        para generar automáticamente los metadatos del evento.
        """
        # Llamar al __post_init__ de la clase base para generar metadatos
        super().__post_init__()

    def __str__(self) -> str:
        """
        Representación string legible del evento.

        Returns:
            String descriptivo del evento para logging y debugging
        """
        return (
            f"UserLoggedOutEvent("
            f"user_id={self.user_id}, "
            f"logged_out_at={self.logged_out_at}, "
            f"token_present={self.token_used is not None})"
        )

    def to_dict(self) -> dict:
        """
        Convierte el evento a diccionario para serialización.

        Extiende el to_dict() de la clase base con campos específicos del logout.

        Returns:
            Diccionario con todos los datos del evento
        """
        # Obtener diccionario base y agregar campos específicos
        base_dict = super().to_dict()
        base_dict.update(
            {
                "user_id": self.user_id,
                "logged_out_at": self.logged_out_at.isoformat(),
                "token_used": self.token_used,
                "ip_address": self.ip_address,
                "user_agent": self.user_agent,
            }
        )
        return base_dict
