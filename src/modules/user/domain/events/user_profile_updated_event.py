"""
User Profile Updated Event - Users Domain Layer

Evento de dominio que representa la actualización de información personal del usuario.
Este evento se dispara cuando un usuario actualiza su nombre o apellidos.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class UserProfileUpdatedEvent(DomainEvent):
    """
    Evento que indica que un usuario ha actualizado su información personal.

    Este evento se emite cuando el usuario cambia sus datos no sensibles
    como nombre y apellidos. NO incluye cambios en email o password.

    Attributes:
        user_id: ID del usuario que actualizó su perfil
        old_first_name: Nombre anterior (puede ser None si no cambió)
        new_first_name: Nuevo nombre (puede ser None si no cambió)
        old_last_name: Apellido anterior (puede ser None si no cambió)
        new_last_name: Nuevo apellido (puede ser None si no cambió)
        updated_at: Timestamp de la actualización
    """

    # Datos del usuario (CAMPOS OBLIGATORIOS)
    user_id: str
    updated_at: datetime

    # Datos del perfil (CAMPOS OPCIONALES - al menos uno debe cambiar)
    old_first_name: str | None = None
    new_first_name: str | None = None
    old_last_name: str | None = None
    new_last_name: str | None = None
    old_country_code: str | None = None
    new_country_code: str | None = None

    @property
    def aggregate_id(self) -> str:
        """El ID del agregado es el ID del usuario."""
        return self.user_id

    @property
    def has_first_name_change(self) -> bool:
        """Verifica si el nombre cambió."""
        return self.old_first_name != self.new_first_name

    @property
    def has_last_name_change(self) -> bool:
        """Verifica si el apellido cambió."""
        return self.old_last_name != self.new_last_name

    def to_dict(self) -> dict:
        """
        Serialización específica para UserProfileUpdatedEvent.

        Extiende la serialización base con campos específicos del evento.
        """
        base_dict = super().to_dict()
        base_dict.update(
            {
                "profile_changes": {
                    "first_name": {
                        "old": self.old_first_name,
                        "new": self.new_first_name,
                        "changed": self.has_first_name_change,
                    },
                    "last_name": {
                        "old": self.old_last_name,
                        "new": self.new_last_name,
                        "changed": self.has_last_name_change,
                    },
                },
                "updated_at": self.updated_at.isoformat(),
            }
        )
        return base_dict

    def __str__(self) -> str:
        """Representación string legible del evento."""
        changes = []
        if self.has_first_name_change:
            changes.append(f"first_name: {self.old_first_name} -> {self.new_first_name}")
        if self.has_last_name_change:
            changes.append(f"last_name: {self.old_last_name} -> {self.new_last_name}")

        changes_str = ", ".join(changes)
        return f"UserProfileUpdatedEvent(user_id={self.user_id}, changes=[{changes_str}])"
