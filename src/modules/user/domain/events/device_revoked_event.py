"""
Domain Event disparado cuando un usuario revoca un dispositivo.

Este evento se emite cuando un usuario elimina/revoca un dispositivo
desde su lista de dispositivos activos (ej: dispositivo perdido/robado).

Propósito:
- Notificar que el usuario tomó una acción de seguridad
- Permitir a event handlers tomar acciones (logging, invalidar sesiones)
- Desacoplar lógica de negocio de efectos secundarios

Event Handlers típicos:
- SessionInvalidationHandler: Invalida refresh tokens del dispositivo
- SecurityLogger: Registra la revocación en audit trail
- AnalyticsHandler: Registra métrica de dispositivos revocados
"""

from dataclasses import dataclass

from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class DeviceRevokedEvent(DomainEvent):
    """
    Evento de dominio emitido cuando un dispositivo es revocado.

    Se dispara automáticamente cuando:
    1. Usuario ejecuta acción de revocar dispositivo (DELETE /devices/{id})
    2. Se llama al método device.revoke() en la entidad
    3. Se marca el dispositivo como is_active=False

    Información incluida:
    - user_id: Identifica al usuario que revocó
    - device_id: ID del dispositivo revocado
    - device_name: Nombre del dispositivo (para logging legible)
    - revoked_by_user: True si el usuario lo revocó, False si fue automático
    - occurred_on: Timestamp exacto de la revocación

    Attributes:
        user_id (UserId): ID del usuario propietario del dispositivo
        device_id (UserDeviceId): ID del dispositivo revocado
        device_name (str): Nombre del dispositivo revocado
        revoked_by_user (bool): True si fue acción manual del usuario
        occurred_on (datetime): Timestamp del evento (UTC naive)

    Examples:
        >>> event = DeviceRevokedEvent(
        ...     user_id=UserId.generate(),
        ...     device_id=UserDeviceId.generate(),
        ...     device_name="Chrome on macOS",
        ...     revoked_by_user=True,
        ...     occurred_on=datetime.utcnow()
        ... )
        >>> event.revoked_by_user
        True
    """

    user_id: UserId
    device_id: UserDeviceId
    device_name: str
    revoked_by_user: bool

    def __repr__(self) -> str:
        """
        Representación técnica del evento para debugging.

        Returns:
            str: Representación legible del evento

        Examples:
            >>> event = DeviceRevokedEvent(...)
            >>> repr(event)
            "DeviceRevokedEvent(user_id=UserId(...), device='Chrome on macOS', manual=True)"
        """
        return (
            f"DeviceRevokedEvent("
            f"user_id={self.user_id!r}, "
            f"device='{self.device_name}', "
            f"manual={self.revoked_by_user})"
        )
