# src/modules/user/application/handlers/user_registered_event_handler.py
import logging

from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent
from src.shared.domain.events.event_handler import EventHandler


class UserRegisteredEventHandler(EventHandler[UserRegisteredEvent]):
    """
    Manejador para el evento UserRegisteredEvent.
    Define las acciones a realizar cuando un usuario se registra.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    @property
    def event_type(self) -> type[UserRegisteredEvent]:
        return UserRegisteredEvent

    async def handle(self, event: UserRegisteredEvent) -> None:
        """Procesa el evento de registro de usuario."""
        self._logger.info(f"Processing user registration for {event.full_name} ({event.email})")

        # Aquí irían las acciones concretas:
        await self._send_welcome_email(event)
        await self._log_registration(event)
        await self._notify_external_systems(event)

        self._logger.info(f"Successfully processed user registration for {event.email}")

    async def _send_welcome_email(self, event: UserRegisteredEvent) -> None:
        """Simula el envío de un email de bienvenida."""
        self._logger.info(f"📧 Sending welcome email to {event.email}")
        # Lógica de envío de email aquí...

    async def _log_registration(self, event: UserRegisteredEvent) -> None:
        """Registra la auditoría del registro de usuario."""
        self._logger.info(f"📝 Logging user registration for {event.user_id}")
        # Lógica de auditoría aquí...

    async def _notify_external_systems(self, event: UserRegisteredEvent) -> None:
        """Notifica a sistemas externos sobre el nuevo registro."""
        self._logger.info(f"🔔 Notifying external systems about user {event.user_id}")
        # Lógica de notificación aquí...
