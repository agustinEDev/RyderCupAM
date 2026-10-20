"""PartidaId Value Object - Identificador de una partida de stroke play (#251)."""

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True)
class PartidaId:
    """Identificador unico de una partida."""

    value: UUID

    def __post_init__(self):
        if not isinstance(self.value, UUID):
            raise TypeError(f"PartidaId debe ser UUID, no {type(self.value).__name__}")

    @classmethod
    def generate(cls) -> "PartidaId":
        """Genera un identificador nuevo."""
        return cls(uuid4())

    def __lt__(self, other: "PartidaId") -> bool:
        """Ordena por su UUID: SQLAlchemy lo pide al borrar varias de una vez (ver EnvelopeId)."""
        if not isinstance(other, PartidaId):
            return NotImplemented
        return self.value < other.value

    def __str__(self) -> str:
        return str(self.value)
