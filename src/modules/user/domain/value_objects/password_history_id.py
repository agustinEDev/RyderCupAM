"""
Password History ID Value Object - Domain Layer

Identifica de manera única cada registro de historial de contraseñas.
"""

import uuid


class PasswordHistoryId:
    """
    Value Object para el identificador único de un registro de historial de contraseñas.

    Representa un UUID que identifica de manera única cada cambio de contraseña registrado.
    Sigue los mismos principios que UserId para consistencia en el dominio.

    Attributes:
        value (uuid.UUID): El identificador UUID único

    Raises:
        ValueError: Si el valor no es un UUID válido
    """

    def __init__(self, value: uuid.UUID | str):
        """
        Inicializa el PasswordHistoryId.

        Args:
            value: UUID como objeto UUID o string

        Raises:
            ValueError: Si el valor no es un UUID válido
        """
        if isinstance(value, str):
            try:
                self.value = uuid.UUID(value)
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"Invalid UUID format: {value}") from exc
        elif isinstance(value, uuid.UUID):
            self.value = value
        else:
            raise ValueError(f"PasswordHistoryId must be UUID or string, got {type(value)}")

    @classmethod
    def generate(cls) -> "PasswordHistoryId":
        """
        Genera un nuevo PasswordHistoryId con UUID v4 aleatorio.

        Returns:
            PasswordHistoryId: Nueva instancia con UUID único

        Example:
            >>> history_id = PasswordHistoryId.generate()
            >>> isinstance(history_id.value, uuid.UUID)
            True
        """
        return cls(uuid.uuid4())

    def __eq__(self, other: object) -> bool:
        """Compara dos PasswordHistoryId por valor."""
        if not isinstance(other, PasswordHistoryId):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        """Permite usar PasswordHistoryId como clave de diccionario."""
        return hash(self.value)

    def __str__(self) -> str:
        """Representación string del UUID."""
        return str(self.value)

    def __repr__(self) -> str:
        """Representación para debugging."""
        return f"PasswordHistoryId('{self.value}')"
