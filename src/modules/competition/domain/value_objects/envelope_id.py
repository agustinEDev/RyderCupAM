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

    def __lt__(self, other: "EnvelopeId") -> bool:
        """Ordena por su UUID.

        Lo pide SQLAlchemy: para vaciar una sesion ordena por clave primaria
        los objetos que va a borrar, y sin esto reventaba con
        `InvalidRequestError` al borrar los DOS sobres de una vez (visto en el
        Kind el 23 sep, al rehacerlos). Con uno solo no hay nada que ordenar y
        no se notaba. `RoundId` y `MatchId` ya lo tenian; `DraftId` no lo
        necesita, porque solo hay un draft por competicion.
        """
        if not isinstance(other, EnvelopeId):
            return NotImplemented
        return self.value < other.value

    def __str__(self) -> str:
        return str(self.value)
