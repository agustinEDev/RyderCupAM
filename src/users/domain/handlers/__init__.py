# -*- coding: utf-8 -*-
"""
User Domain Handlers - Event handlers para el dominio User.

Expone los handlers específicos para eventos del dominio de usuarios.
"""

from .user_registered_event_handler import UserRegisteredEventHandler

__all__ = [
    "UserRegisteredEventHandler",
]