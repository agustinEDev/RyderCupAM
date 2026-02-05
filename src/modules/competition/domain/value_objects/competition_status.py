"""
CompetitionStatus Value Object - Estado del ciclo de vida de una competición.

Define los estados posibles de una competición desde su creación hasta su finalización.
"""

from enum import Enum, StrEnum


class CompetitionStatus(StrEnum):
    """
    Enum para los estados del ciclo de vida de una competición.

    Estados:
    - DRAFT: Borrador, en configuración inicial
    - ACTIVE: Activa, inscripciones abiertas
    - CLOSED: Cerrada, inscripciones cerradas pero no empezó
    - IN_PROGRESS: En curso, el torneo está en desarrollo
    - COMPLETED: Finalizada
    - CANCELLED: Cancelada

    Transiciones válidas:
    DRAFT → ACTIVE → CLOSED → IN_PROGRESS → COMPLETED
               ↓         ↓          ↓
           CANCELLED  CANCELLED  CANCELLED
    """

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    def can_transition_to(self, new_status: "CompetitionStatus") -> bool:
        """
        Verifica si es válida la transición al nuevo estado.

        Args:
            new_status: Estado destino

        Returns:
            bool: True si la transición es válida, False en caso contrario

        Ejemplos:
            >>> CompetitionStatus.DRAFT.can_transition_to(CompetitionStatus.ACTIVE)
            True
            >>> CompetitionStatus.COMPLETED.can_transition_to(CompetitionStatus.DRAFT)
            False
        """
        valid_transitions = {
            CompetitionStatus.DRAFT: {
                CompetitionStatus.ACTIVE,
                CompetitionStatus.CANCELLED,
            },
            CompetitionStatus.ACTIVE: {
                CompetitionStatus.CLOSED,
                CompetitionStatus.CANCELLED,
            },
            CompetitionStatus.CLOSED: {
                CompetitionStatus.IN_PROGRESS,
                CompetitionStatus.CANCELLED,
            },
            CompetitionStatus.IN_PROGRESS: {
                CompetitionStatus.COMPLETED,
                CompetitionStatus.CANCELLED,
            },
            CompetitionStatus.COMPLETED: set(),  # Estado final
            CompetitionStatus.CANCELLED: set(),  # Estado final
        }

        return new_status in valid_transitions.get(self, set())

    def is_active(self) -> bool:
        """Verifica si el estado permite inscripciones."""
        return self == CompetitionStatus.ACTIVE

    def is_final(self) -> bool:
        """Verifica si es un estado final (no permite más transiciones)."""
        return self in {CompetitionStatus.COMPLETED, CompetitionStatus.CANCELLED}

    def allows_modifications(self) -> bool:
        """Verifica si el estado permite modificar la configuración."""
        return self == CompetitionStatus.DRAFT

    def __composite_values__(self):
        """
        Retorna los valores para SQLAlchemy composite mapping.

        Requerido para que SQLAlchemy pueda persistir el Value Object.
        """
        return (self.value,)
