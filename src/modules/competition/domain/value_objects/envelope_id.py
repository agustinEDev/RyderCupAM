"""EnvelopeId Value Object - Identificador de un sobre (FE #655)."""

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True)
class EnvelopeId:
    """Identificador unico de un sobre."""

    value: UUID

    def __post_init__(self):
        if not isinstance(self.value, UUID):
            raise TypeError(f"EnvelopeId debe ser UUID, no {type(self.value).__name__}")

    @classmethod
    def generate(cls) -> "EnvelopeId":
        """Genera un identificador nuevo."""
        return cls(uuid4())

    def __str__(self) -> str:
        return str(self.value)
