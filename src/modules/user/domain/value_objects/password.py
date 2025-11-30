"""
Password Value Object - Password seguro con hashing y validación.

Este Value Object representa un password hasheado y validado.
"""

import os
from dataclasses import dataclass

import bcrypt


class InvalidPasswordError(Exception):
    """Excepción lanzada cuando un password no es válido."""
    pass


@dataclass(frozen=True)
class Password:
    """
    Value Object para passwords hasheados.

    Almacena el hash, no el password original.
    """

    MIN_LENGTH = 8
    hashed_value: str

    @classmethod
    def from_plain_text(cls, plain_password: str) -> 'Password':
        """
        Crea Password desde texto plano.
        Valida fortaleza y hashea automáticamente.
        """
        if not cls._is_strong_password(plain_password):
            raise InvalidPasswordError("Password no cumple requisitos de seguridad")

        hashed = cls._hash_password(plain_password)
        return cls(hashed)

    @staticmethod
    def _hash_password(plain_password: str) -> str:
        """Hashea password con bcrypt y salt."""
        # Usar rounds más bajo para tests (detecta si estamos en testing)
        rounds = 4 if os.getenv('TESTING') == 'true' else 12
        salt = bcrypt.gensalt(rounds=rounds)
        hashed = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def _is_strong_password(password: str) -> bool:
        """Valida si el password cumple requisitos de seguridad."""
        if not isinstance(password, str) or len(password) < Password.MIN_LENGTH:
            return False

        # Al menos una mayúscula, una minúscula y un número
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)

        return has_upper and has_lower and has_digit

    def verify(self, plain_password: str) -> bool:
        """Verifica si un password plano coincide con el hash."""
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                self.hashed_value.encode('utf-8')
            )
        except Exception:
            return False

    def __str__(self) -> str:
        """Representación string segura (sin mostrar hash)."""
        return "[Password Hash]"

    def __eq__(self, other) -> bool:
        """Operador de igualdad."""
        return isinstance(other, Password) and self.hashed_value == other.hashed_value

    def __hash__(self) -> int:
        """Hash del objeto - Permite usar en sets y como keys de dict."""
        return hash(self.hashed_value)
