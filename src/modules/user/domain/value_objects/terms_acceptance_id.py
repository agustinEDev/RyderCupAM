"""
Terms Acceptance ID Value Object - Domain Layer

Identifica cada fila del historial de aceptaciones de los Términos.
"""

import uuid


class TermsAcceptanceId:
    """UUID de una aceptación de los Términos. Mismo patrón que PasswordHistoryId."""

    def __init__(self, value: uuid.UUID | str):
        if isinstance(value, str):
            try:
                self.value = uuid.UUID(value)
            except (ValueError, AttributeError) as exc:
                raise ValueError(f"Invalid UUID format: {value}") from exc
        elif isinstance(value, uuid.UUID):
            self.value = value
        else:
            raise ValueError(f"TermsAcceptanceId must be UUID or string, got {type(value)}")

    @classmethod
    def generate(cls) -> "TermsAcceptanceId":
        """Un id nuevo (UUID v4)."""
        return cls(uuid.uuid4())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TermsAcceptanceId):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"TermsAcceptanceId('{self.value}')"
