# -*- coding: utf-8 -*-
"""
Handler para el evento UserRegisteredEvent.

Este handler maneja los efectos secundarios que deben ocurrir
cuando un usuario se registra en el sistema.
"""

import logging
from typing import Type

from src.shared.domain.events.event_handler import EventHandler, EventType
from src.users.domain.events.user_registered_event import UserRegisteredEvent

logger = logging.getLogger(__name__)


class UserRegisteredEventHandler(EventHandler[UserRegisteredEvent]):
    """
    Handler para eventos de registro de usuario.
    
    Responsabilidades:
    - Enviar email de bienvenida (simulado)
    - Logging del registro
    - Notificaciones internas
    - Integración con sistemas externos
    """
    
    def __init__(self):
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def handle(self, event: UserRegisteredEvent) -> None:
        """
        Maneja el evento de registro de usuario.
        
        Args:
            event: El evento UserRegisteredEvent
        """
        self._logger.info(
            f"Processing user registration for {event.full_name} ({event.email})",
            extra={
                "user_id": event.user_id,
                "email": event.email,
                "event_id": event.event_id,
                "aggregate_id": event.aggregate_id
            }
        )
        
        # Simular envío de email de bienvenida
        await self._send_welcome_email(event)
        
        # Simular logging del registro
        await self._log_registration(event)
        
        # Simular notificación a sistemas externos
        await self._notify_external_systems(event)
        
        self._logger.info(
            f"Successfully processed user registration for {event.user_id}",
            extra={"user_id": event.user_id, "event_id": event.event_id}
        )
    
    @property
    def event_type(self) -> Type[UserRegisteredEvent]:
        """
        Retorna el tipo de evento que maneja este handler.
        
        Returns:
            Type[UserRegisteredEvent]: La clase UserRegisteredEvent
        """
        return UserRegisteredEvent
    
    async def _send_welcome_email(self, event: UserRegisteredEvent) -> None:
        """
        Simula el envío de un email de bienvenida.
        
        Args:
            event: El evento de registro
        """
        self._logger.info(
            f"📧 Sending welcome email to {event.email}",
            extra={
                "action": "send_welcome_email",
                "recipient": event.email,
                "user_name": event.full_name
            }
        )
        
        # Aquí iría la integración real con un servicio de email
        # Por ejemplo: SendGrid, SES, etc.
        # await email_service.send_welcome_email(event.email, event.full_name)
    
    async def _log_registration(self, event: UserRegisteredEvent) -> None:
        """
        Registra el evento de registro para auditoría.
        
        Args:
            event: El evento de registro
        """
        self._logger.info(
            f"📝 Logging user registration",
            extra={
                "action": "log_registration",
                "user_id": event.user_id,
                "timestamp": event.occurred_on.isoformat(),
                "event_version": event.event_version
            }
        )
        
        # Aquí iría la integración con sistema de auditoría
        # await audit_service.log_user_registration(event)
    
    async def _notify_external_systems(self, event: UserRegisteredEvent) -> None:
        """
        Notifica a sistemas externos sobre el nuevo registro.
        
        Args:
            event: El evento de registro
        """
        self._logger.info(
            f"🔔 Notifying external systems about user registration",
            extra={
                "action": "notify_external_systems",
                "user_id": event.user_id,
                "systems": ["crm", "analytics", "notification_service"]
            }
        )
        
        # Aquí irían las integraciones con sistemas externos
        # await crm_service.create_customer(event)
        # await analytics_service.track_registration(event)
        # await notification_service.send_admin_notification(event)