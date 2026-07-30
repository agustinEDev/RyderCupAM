"""
User Avatar Upload ID Value Object - Domain Layer

Identifica de manera única cada foto de avatar subida por un usuario.
"""

import uuid


class UserAvatarUploadId:
    """
    Value Object para el identificador único de una foto de avatar subida.

    Sigue los mismos principios que PasswordHistoryId para consistencia en el dominio.
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
            raise ValueError(f"UserAvatarUploadId must be UUID or string, got {type(value)}")

    @classmethod
    def generate(cls) -> "UserAvatarUploadId":
        """Genera un nuevo UserAvatarUploadId con UUID v4 aleatorio."""
        return cls(uuid.uuid4())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UserAvatarUploadId):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"UserAvatarUploadId('{self.value}')"
