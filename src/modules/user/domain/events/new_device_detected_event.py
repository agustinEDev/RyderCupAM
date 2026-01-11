"""
Domain Event disparado cuando se detecta un dispositivo nuevo.

Este evento se emite cuando un usuario hace login desde un dispositivo
que nunca antes se había utilizado para acceder a su cuenta.

Propósito:
- Notificar que ocurrió una acción de seguridad importante
- Permitir a event handlers tomar acciones (email, logging, analytics)
- Desacoplar lógica de negocio de efectos secundarios

Event Handlers típicos:
- EmailHandler: Envía email de notificación al usuario
- SecurityLogger: Registra el evento en audit trail
- AnalyticsHandler: Registra métrica de nuevos dispositivos
"""

from dataclasses import dataclass

from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class NewDeviceDetectedEvent(DomainEvent):
    """
    Evento de dominio emitido cuando se detecta un dispositivo nuevo.

    Se dispara automáticamente cuando:
    1. Usuario hace login exitoso
    2. El fingerprint del dispositivo NO existe en la BD
    3. Se crea un nuevo registro UserDevice

    Información incluida:
    - user_id: Identifica al usuario afectado
    - device_name: Nombre legible del dispositivo ("Chrome on macOS")
    - ip_address: IP desde donde se conectó (para mostrar en email)
    - user_agent: User-Agent completo (para logging/debugging)
    - occurred_on: Timestamp exacto de la detección

    Attributes:
        user_id (UserId): ID del usuario que hizo login
        device_name (str): Nombre generado automáticamente del dispositivo
        ip_address (str): Dirección IP del dispositivo
        user_agent (str): User-Agent HTTP header completo
        occurred_on (datetime): Timestamp del evento (UTC naive)

    Examples:
        >>> from src.modules.user.domain.value_objects.user_id import UserId
        >>> event = NewDeviceDetectedEvent(
        ...     user_id=UserId.generate(),
        ...     device_name="Chrome on macOS",
        ...     ip_address="192.168.1.100",
        ...     user_agent="Mozilla/5.0 (Macintosh)...",
        ...     occurred_on=datetime.utcnow()
        ... )
        >>> event.device_name
        'Chrome on macOS'
    """

    user_id: UserId
    device_name: str
    ip_address: str
    user_agent: str

    def __repr__(self) -> str:
        """
        Representación técnica del evento para debugging.

        Returns:
            str: Representación legible del evento

        Examples:
            >>> event = NewDeviceDetectedEvent(...)
            >>> repr(event)
            "NewDeviceDetectedEvent(user_id=UserId(...), device='Chrome on macOS', ip='192.168.1.100')"
        """
        return (
            f"NewDeviceDetectedEvent("
            f"user_id={self.user_id!r}, "
            f"device='{self.device_name}', "
            f"ip='{self.ip_address}')"
        )
