"""
Domain Event Base - Shared Domain Layer

Clase base abstracta para todos los eventos de dominio del sistema.
Los eventos de dominio representan algo importante que ha ocurrido en el negocio.
"""

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
import uuid


@dataclass(frozen=True)
class DomainEvent(ABC):
    """
    Clase base abstracta para todos los eventos de dominio.
    
    Los eventos de dominio representan algo importante que ha ocurrido
    en el dominio y que otros contextos acotados pueden necesitar saber.
    
    Características:
    - Inmutables (frozen=True)  
    - Tienen un ID único automático
    - Incluyen timestamp de cuándo ocurrieron
    - Tienen un número de versión para evolución del esquema
    - Son serializables a diccionario
    
    Esta clase base no define campos específicos. Los metadatos
    se generan automáticamente en __post_init__ de cada subclase.
    """
    
    def __post_init__(self):
        """
        Genera automáticamente los metadatos del evento.
        
        Este método se ejecuta después de la inicialización del dataclass
        y añade los campos de metadatos necesarios para todos los eventos.
        """
        # Generar metadatos automáticamente usando nombres internos
        object.__setattr__(self, '_event_id', str(uuid.uuid4()))
        object.__setattr__(self, '_occurred_on', datetime.now())
        object.__setattr__(self, '_event_version', 1)
        
        # Si la subclase no define aggregate_id, usar el primer campo
        # como convención (típicamente user_id, team_id, etc.)
        aggregate_id_value = ''
        for field_name, field_value in self.__dict__.items():
            if field_name.endswith('_id') and field_value and not field_name.startswith('_'):
                aggregate_id_value = field_value
                break
        
        object.__setattr__(self, '_aggregate_id', aggregate_id_value)
    
    @property
    def event_id(self) -> str:
        """ID único del evento."""
        return getattr(self, '_event_id', '')
    
    @property  
    def occurred_on(self) -> datetime:
        """Timestamp de cuándo ocurrió el evento."""
        return getattr(self, '_occurred_on', datetime.now())
    
    @property
    def event_version(self) -> int:
        """Versión del esquema del evento."""
        return getattr(self, '_event_version', 1)
    
    @property
    def aggregate_id(self) -> str:
        """ID del agregado que generó el evento."""
        return getattr(self, '_aggregate_id', '')
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el evento a diccionario para serialización.
        
        Útil para persistencia, logging o envío por red.
        
        Returns:
            Dict con todos los datos del evento
        """
        return {
            'event_id': self.event_id,
            'event_type': self.__class__.__name__,
            'aggregate_id': self.aggregate_id,
            'occurred_on': self.occurred_on.isoformat(),
            'event_version': self.event_version,
            'data': {
                key: value for key, value in self.__dict__.items()
                if key not in ['event_id', 'occurred_on', 'event_version', 'aggregate_id']
            }
        }
    
    def __str__(self) -> str:
        """Representación string legible del evento."""
        return f"{self.__class__.__name__}(id={self.event_id[:8]}..., aggregate={self.aggregate_id})"
    
    def __repr__(self) -> str:
        """Representación detallada para debugging."""
        return (
            f"{self.__class__.__name__}("
            f"event_id='{self.event_id}', "
            f"aggregate_id='{self.aggregate_id}', "
            f"occurred_on='{self.occurred_on.isoformat()}'"
            f")"
        )