from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List

from ..value_objects.user_id import UserId
from ..value_objects.email import Email
from ..value_objects.password import Password
from src.shared.domain.events.domain_event import DomainEvent


@dataclass
class User:
    """
    Entidad User - Representa un usuario en el sistema.
    
    Un usuario es alguien que puede registrarse, hacer login
    y participar en torneos Ryder Cup.
    """
    
    # Identificador único usando Value Object
    id: Optional[UserId] = None
    
    # Campos básicos usando Value Objects
    email: Optional[Email] = None
    password: Optional[Password] = None
    first_name: str = ""
    last_name: str = ""
    
    # TODO: ¿Cómo manejar las fechas?
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Colección de eventos de dominio
    _domain_events: List[DomainEvent] = field(default_factory=list, init=False)
    
    def get_full_name(self) -> str:
        """Devuelve el nombre completo del usuario."""
        return f"{self.first_name} {self.last_name}".strip()
    
    def has_valid_email(self) -> bool:
        """Verifica si el usuario tiene un email válido."""
        return self.email is not None
    
    def is_valid(self) -> bool:
        """Verifica si el usuario es válido (todos los campos requeridos)."""
        return (
            self.has_valid_email() and
            self.first_name.strip() != "" and
            self.last_name.strip() != "" and
            self.password is not None
        )
    
    def verify_password(self, plain_password: str) -> bool:
        """Verifica si el password plano coincide con el hasheado."""
        if self.password is None:
            return False
        return self.password.verify(plain_password)
    
    @classmethod
    def create(cls, first_name: str, last_name: str, email_str: str, plain_password: str) -> 'User':
        """
        Factory method para crear usuario con Value Objects.
        
        Args:
            first_name: Nombre del usuario
            last_name: Apellido del usuario  
            email_str: Email en formato string
            plain_password: Password en texto plano
            
        Returns:
            User: Nueva instancia con ID generado y Value Objects
        """
        user_id = UserId.generate()
        email = Email(email_str)
        password = Password.from_plain_text(plain_password)
        
        user = cls(
            id=user_id,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Generar evento de registro
        from src.users.domain.events.user_registered_event import UserRegisteredEvent
        user._add_domain_event(UserRegisteredEvent(
            user_id=str(user_id.value),
            email=email_str,
            name=first_name,
            surname=last_name
        ))
        
        return user
    
    # === Métodos para manejo de eventos de dominio ===
    
    def _add_domain_event(self, event: DomainEvent) -> None:
        """Agrega un evento de dominio a la colección interna."""
        self._domain_events.append(event)
    
    def get_domain_events(self) -> List[DomainEvent]:
        """Obtiene una copia de todos los eventos de dominio pendientes."""
        return self._domain_events.copy()
    
    def clear_domain_events(self) -> None:
        """Limpia todos los eventos de dominio de la colección."""
        self._domain_events.clear()
    
    def has_domain_events(self) -> bool:
        """Verifica si la entidad tiene eventos de dominio pendientes."""
        return len(self._domain_events) > 0
    
    def __str__(self) -> str:
        """Representación string del usuario (sin mostrar password)."""
        return f"User(id={self.id}, email={self.email}, name={self.get_full_name()})"