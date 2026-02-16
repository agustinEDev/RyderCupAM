"""
OAuth Account ID Value Object - Domain Layer

Identifica de manera única cada cuenta OAuth vinculada a un usuario.
"""

import uuid


class OAuthAccountId:
    """
    Value Object para el identificador único de una cuenta OAuth vinculada.

    Attributes:
        value (uuid.UUID): El identificador UUID único

    Raises:
        ValueError: Si el valor no es un UUID válido
    """

    def __init__(self, value: uuid.UUID | str):
        if isinstance(value, str):
            try:
                self.value = uuid.UUID(value)
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"Invalid UUID format: {value}") from exc
        elif isinstance(value, uuid.UUID):
            self.value = value
        else:
            raise ValueError(f"OAuthAccountId must be UUID or string, got {type(value)}")

    @classmethod
    def generate(cls) -> "OAuthAccountId":
        """Genera un nuevo OAuthAccountId con UUID v4 aleatorio."""
        return cls(uuid.uuid4())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OAuthAccountId):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"OAuthAccountId('{self.value}')"
