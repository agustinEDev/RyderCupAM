"""
Domain Events - Users Module

Eventos de dominio específicos del módulo de usuarios.
Representan eventos importantes que ocurren en el ciclo de vida de los usuarios.
"""

from .user_registered_event import UserRegisteredEvent

__all__ = [
    'UserRegisteredEvent',
]