"""
User Logged In Event - Users Domain Layer

Evento de dominio que representa el inicio de sesión exitoso de un usuario.
Este evento se dispara cuando un usuario hace login exitoso en el sistema.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class UserLoggedInEvent(DomainEvent):
    """
    Evento que indica que un usuario ha iniciado sesión exitosamente en el sistema.
    
    Este evento contiene información relevante del login y puede ser usado 
    por otros bounded contexts para realizar acciones como:
    - Auditoría de seguridad
    - Analytics de sesiones
    - Detección de actividad sospechosa
    - Notificaciones de acceso
    - Tracking de uso de la aplicación
    
    Attributes:
        user_id: ID específico del usuario (se usa como aggregate_id automáticamente)
        logged_in_at: Timestamp exacto del login exitoso
        ip_address: Dirección IP desde donde se hizo login (opcional)
        user_agent: User agent del browser/app (opcional)
        session_id: ID de la sesión creada (opcional, para tracking)
        login_method: Método usado para login (email/social) (opcional)
    """
    
    user_id: str
    logged_in_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    login_method: Optional[str] = None

    def __post_init__(self):
        """
        Post-inicialización que llama al __post_init__ de la clase base
        para generar automáticamente los metadatos del evento.
        """
        # Llamar al __post_init__ de la clase base para generar metadatos
        super().__post_init__()

    def __str__(self) -> str:
        """
        Representación string del evento para logging y debugging.
        
        Returns:
            String descriptivo del evento sin exponer datos sensibles
        """
        return (
            f"UserLoggedInEvent(user_id={self.user_id}, "
            f"logged_in_at={self.logged_in_at.isoformat()}, "
            f"ip_address={self.ip_address or 'Unknown'}, "
            f"login_method={self.login_method or 'email'})"
        )

    def to_dict(self) -> dict:
        """
        Convierte el evento a diccionario para serialización.
        
        Útil para almacenamiento, logging, y comunicación entre servicios.
        Incluye tanto los datos del evento como los metadatos base.
        
        Returns:
            Diccionario con todos los campos del evento y metadatos
        """
        return {
            # Datos específicos del evento
            "user_id": self.user_id,
            "logged_in_at": self.logged_in_at.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "login_method": self.login_method,
            
            # Metadatos base del evento (generados automáticamente)
            "event_id": getattr(self, '_event_id', None),
            "occurred_on": getattr(self, '_occurred_on', None).isoformat() if hasattr(self, '_occurred_on') else None,
            "event_version": getattr(self, '_event_version', None),
            "aggregate_id": getattr(self, '_aggregate_id', None),
        }