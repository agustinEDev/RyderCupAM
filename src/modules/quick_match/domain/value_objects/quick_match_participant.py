"""
QuickMatchParticipant Value Object - Participante de una partida rapida.

Admite dos variantes:
- Registrado: tiene `user_id`, sin datos manuales.
- Invitado: sin cuenta, con nombre/apellidos y handicap introducidos a mano.

Ambas comparten `participant_id` como identificador estable (coincide con
`user_id.value` para registrados; generado para invitados), usado para
listar, eliminar y asignar anotador independientemente del tipo.
"""

from dataclasses import dataclass

from src.modules.user.domain.value_objects.user_id import UserId

from .participant_id import ParticipantId

VALID_TEAMS = {"A", "B"}
MIN_HANDICAP = -10.0
MAX_HANDICAP = 54.0


@dataclass(frozen=True)
class QuickMatchParticipant:
    """
    Value Object que representa a un jugador dentro de una partida rapida.

    - `team` es None para SINGLES (no hay equipos), "A" o "B" para FOURBALL/FOURSOMES.
    - Registrado: `user_id` presente, `first_name`/`last_name`/`handicap` None.
    - Invitado: `user_id` None, `first_name`/`last_name` obligatorios, `handicap` opcional.
    """

    participant_id: ParticipantId
    user_id: UserId | None
    first_name: str | None
    last_name: str | None
    handicap: float | None
    team: str | None = None

    def __post_init__(self):
        if self.team is not None and self.team not in VALID_TEAMS:
            raise ValueError(f"team debe ser 'A', 'B' o None, recibido: {self.team!r}")

        if self.user_id is not None:
            if self.first_name is not None or self.last_name is not None:
                raise ValueError("Un participante registrado no lleva first_name/last_name.")
            if self.handicap is not None:
                raise ValueError("Un participante registrado no lleva handicap manual.")
        else:
            if not self.first_name or not self.first_name.strip():
                raise ValueError("Un participante invitado requiere first_name.")
            if not self.last_name or not self.last_name.strip():
                raise ValueError("Un participante invitado requiere last_name.")

        if self.handicap is not None and not (MIN_HANDICAP <= self.handicap <= MAX_HANDICAP):
            raise ValueError(f"handicap debe estar entre {MIN_HANDICAP} y {MAX_HANDICAP}.")

    @property
    def is_guest(self) -> bool:
        return self.user_id is None

    @classmethod
    def for_user(cls, user_id: UserId, team: str | None = None) -> "QuickMatchParticipant":
        """Crea un participante registrado (identificado por su UserId)."""
        return cls(
            participant_id=ParticipantId(user_id.value),
            user_id=user_id,
            first_name=None,
            last_name=None,
            handicap=None,
            team=team,
        )

    @classmethod
    def for_guest(
        cls,
        first_name: str,
        last_name: str,
        handicap: float | None = None,
        team: str | None = None,
    ) -> "QuickMatchParticipant":
        """Crea un participante invitado (sin cuenta de usuario)."""
        return cls(
            participant_id=ParticipantId.generate(),
            user_id=None,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            handicap=handicap,
            team=team,
        )

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, QuickMatchParticipant)
            and self.participant_id == other.participant_id
        )

    def __hash__(self) -> int:
        return hash(self.participant_id)
