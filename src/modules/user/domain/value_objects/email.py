# -*- coding: utf-8 -*-
"""
Email Value Object - Dirección de email válida y normalizada.

Este Value Object representa una dirección de email.
"""

import re
from dataclasses import dataclass


class InvalidEmailError(Exception):
    """Excepción lanzada cuando un email no es válido."""
    pass


@dataclass(frozen=True)
class Email:
    """
    Value Object para direcciones de email.
    
    Inmutable y validado automáticamente.
    """
    
    value: str
    
    def __post_init__(self):
        """Validación y normalización automática."""
        normalized = self._normalize_email(self.value)
        if not self._is_valid_email(normalized):
            raise InvalidEmailError(f"'{self.value}' no es un email válido")
        # Usar object.__setattr__ porque la clase es frozen
        object.__setattr__(self, 'value', normalized)
    
    @staticmethod
    def _normalize_email(email: str) -> str:
        """Normaliza el email: lowercase y sin espacios."""
        if not isinstance(email, str):
            return ""
        return email.strip().lower()
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Valida si un string tiene formato de email válido."""
        if not isinstance(email, str) or not email:
            return False
        
        # Verificar que no empiece o termine con punto
        if email.startswith('.') or email.endswith('.'):
            return False
            
        # Verificar que no tenga puntos consecutivos
        if '..' in email:
            return False
        
        # Patrón más estricto para emails
        # - Parte local: alfanuméricos, puntos, guiones, más y porcentaje (pero no al inicio/final)
        # - Símbolo @
        # - Dominio: alfanuméricos y guiones (pero no al inicio/final), luego punto y TLD
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]*[a-zA-Z0-9]@[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
        
        # Permitir emails de un solo carácter antes del @
        if '@' in email:
            local_part = email.split('@')[0]
            if len(local_part) == 1:
                pattern = r'^[a-zA-Z0-9]@[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
        
        return re.match(pattern, email) is not None
    
    def __str__(self) -> str:
        """Representación string legible."""
        return self.value
    
    def __eq__(self, other) -> bool:
        """Operador de igualdad."""
        return isinstance(other, Email) and self.value == other.value
