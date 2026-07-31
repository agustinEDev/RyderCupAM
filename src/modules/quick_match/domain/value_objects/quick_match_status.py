"""
QuickMatchStatus Value Object - Estado de una partida rapida.
"""

from enum import StrEnum


class QuickMatchStatus(StrEnum):
    """
    Enum para los estados de una partida rapida.

    Estados:
    - PENDING: creada, se pueden añadir/quitar participantes
    - IN_PROGRESS: iniciada, se pueden registrar scores
    - COMPLETED: finalizada
    - CANCELLED: cancelada

    State Machine:
      PENDING -> IN_PROGRESS (roster completo)
              -> CANCELLED
      IN_PROGRESS -> COMPLETED
                   -> CANCELLED
      COMPLETED, CANCELLED son estados terminales.
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    def is_pending(self) -> bool:
        return self == QuickMatchStatus.PENDING

    def is_in_progress(self) -> bool:
        return self == QuickMatchStatus.IN_PROGRESS

    def is_final(self) -> bool:
        return self in {QuickMatchStatus.COMPLETED, QuickMatchStatus.CANCELLED}

    def can_transition_to(self, new_status: "QuickMatchStatus") -> bool:
        valid_transitions = {
            QuickMatchStatus.PENDING: {
                QuickMatchStatus.IN_PROGRESS,
                QuickMatchStatus.CANCELLED,
            },
            QuickMatchStatus.IN_PROGRESS: {
                QuickMatchStatus.COMPLETED,
                QuickMatchStatus.CANCELLED,
            },
            QuickMatchStatus.COMPLETED: set(),
            QuickMatchStatus.CANCELLED: set(),
        }

        return new_status in valid_transitions.get(self, set())
