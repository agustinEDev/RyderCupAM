"""
User Registered Event - Users Domain Layer

Evento de dominio que representa el registro exitoso de un nuevo usuario en el sistema.
Este evento se dispara cuando un usuario se registra por primera vez.
"""

from dataclasses import dataclass

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class UserRegisteredEvent(DomainEvent):
    """
    Evento que indica que un nuevo usuario se ha registrado en el sistema.

    Este evento contiene toda la información relevante del usuario recién registrado
    y puede ser usado por otros bounded contexts para realizar acciones como:
    - Enviar email de bienvenida
    - Crear perfil inicial
    - Registrar analytics
    - Activar integraciones

    Attributes:
        user_id: ID específico del usuario (se usa como aggregate_id automáticamente)
        email: Email del usuario registrado
        first_name: Nombre del usuario
        last_name: Apellido del usuario
        registration_method: Método usado para registrarse (email, google, etc.)
        is_email_verified: Si el email fue verificado al registro
        registration_ip: IP desde donde se registró (opcional por privacidad)
    """

    # Datos específicos del usuario registrado (CAMPOS OBLIGATORIOS)
    user_id: str
    email: str
    first_name: str
    last_name: str

    # Metadatos del registro (CAMPOS OPCIONALES con defaults)
    registration_method: str = "email"  # email, google, facebook, etc.
    is_email_verified: bool = False
    registration_ip: str | None = None

    @property
    def aggregate_id(self) -> str:
        """El ID del agregado es el ID del usuario."""
        return self.user_id

    @property
    def full_name(self) -> str:
        """Nombre completo del usuario registrado."""
        return f"{self.first_name} {self.last_name}".strip()

    def to_dict(self) -> dict:
        """
        Serialización específica para UserRegisteredEvent.

        Extiende la serialización base con campos específicos del evento.
        """
        base_dict = super().to_dict()
        base_dict.update(
            {
                "user_data": {
                    "user_id": self.user_id,
                    "email": self.email,
                    "first_name": self.first_name,
                    "last_name": self.last_name,
                    "full_name": self.full_name,
                },
                "registration_context": {
                    "method": self.registration_method,
                    "email_verified": self.is_email_verified,
                    "ip_address": self.registration_ip,
                },
            }
        )
        return base_dict

    def __str__(self) -> str:
        """Representación string legible del evento."""
        return f"UserRegisteredEvent(user={self.full_name}, email={self.email}, id={self.event_id[:8]}...)"
