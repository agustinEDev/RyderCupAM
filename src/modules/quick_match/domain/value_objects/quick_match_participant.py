"""
QuickMatchParticipant Value Object - Participante de una partida rapida.
"""

from dataclasses import dataclass

from src.modules.user.domain.value_objects.user_id import UserId

VALID_TEAMS = {"A", "B"}


@dataclass(frozen=True)
class QuickMatchParticipant:
    """
    Value Object que representa a un jugador dentro de una partida rapida.

    - `team` es None para SINGLES (no hay equipos).
    - `team` es "A" o "B" para FOURBALL/FOURSOMES.
    """

    user_id: UserId
    team: str | None = None

    def __post_init__(self):
        if self.team is not None and self.team not in VALID_TEAMS:
            raise ValueError(f"team debe ser 'A', 'B' o None, recibido: {self.team!r}")

    def __eq__(self, other) -> bool:
        return isinstance(other, QuickMatchParticipant) and self.user_id == other.user_id

    def __hash__(self) -> int:
        return hash(self.user_id)
