# -*- coding: utf-8 -*-
"""
UserId Value Object - Identificador único para usuarios.

Este Value Object representa el identificador único de un usuario.
"""

import uuid
from dataclasses import dataclass


class InvalidUserIdError(Exception):
    """Excepción lanzada cuando un UserId no es válido."""
    pass


@dataclass(frozen=True)
class UserId:
    """
    Value Object para identificadores únicos de usuario.
    
    Inmutable y validado automáticamente.
    """
    
    value: str
    
    def __post_init__(self):
        """Validación automática después de la inicialización."""
        if not self._is_valid_uuid(self.value):
            raise InvalidUserIdError(f"'{self.value}' no es un UUID válido")
    
    @classmethod
    def generate(cls) -> 'UserId':
        """Genera un nuevo UserId con UUID aleatorio."""
        new_uuid = str(uuid.uuid4())
        return cls(new_uuid)
    
    @staticmethod
    def _is_valid_uuid(uuid_string: str) -> bool:
        """Valida si un string tiene formato UUID válido."""
        if not isinstance(uuid_string, str):
            return False
        try:
            uuid_obj = uuid.UUID(uuid_string)
            return str(uuid_obj) == uuid_string
        except (ValueError, TypeError):
            return False
    
    def __str__(self) -> str:
        """Representación string legible."""
        return self.value
    
    def __eq__(self, other) -> bool:
        """Operador de igualdad."""
        return isinstance(other, UserId) and self.value == other.value