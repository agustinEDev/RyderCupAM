"""
EnrollmentStatus Value Object - Estado de una inscripción en una competición.

Define los estados posibles de la inscripción de un jugador.
"""

from enum import Enum, StrEnum


class EnrollmentStatus(StrEnum):
    """
    Enum para los estados de inscripción de un jugador.

    Estados:
    - REQUESTED: Solicitud enviada por el jugador (pendiente aprobación)
    - INVITED: Invitado por el creador (pendiente aceptación)
    - APPROVED: Aprobado e inscrito en el torneo
    - REJECTED: Solicitud rechazada por el creador
    - CANCELLED: Solicitud/invitación cancelada por el jugador
    - WITHDRAWN: Jugador inscrito se retiró voluntariamente

    Flujos:
    Flujo de solicitud:
      REQUESTED → APPROVED (aprobado por creador)
                | REJECTED (rechazado por creador)
                | CANCELLED (cancelado por jugador)
      APPROVED → WITHDRAWN (retiro voluntario)

    Flujo de invitación:
      INVITED → APPROVED (acepta invitación)
              | REJECTED (creador retira invitación)
              | CANCELLED (jugador declina invitación)
      APPROVED → WITHDRAWN (retiro voluntario)

    Flujo directo (por creador):
      → APPROVED (inscripción directa)
      APPROVED → WITHDRAWN (retiro voluntario)
    """

    REQUESTED = "REQUESTED"  # Jugador solicitó unirse
    INVITED = "INVITED"  # Creador invitó al jugador
    APPROVED = "APPROVED"  # Inscripción aprobada/aceptada
    REJECTED = "REJECTED"  # Solicitud/invitación rechazada por creador
    CANCELLED = "CANCELLED"  # Solicitud/invitación cancelada por jugador
    WITHDRAWN = "WITHDRAWN"  # Jugador inscrito se retiró

    def is_pending(self) -> bool:
        """
        Verifica si el enrollment está pendiente (requiere acción).

        Returns:
            bool: True si está en REQUESTED o INVITED
        """
        return self in {EnrollmentStatus.REQUESTED, EnrollmentStatus.INVITED}

    def is_active(self) -> bool:
        """
        Verifica si el jugador está activamente inscrito.

        Returns:
            bool: True si está APPROVED
        """
        return self == EnrollmentStatus.APPROVED

    def is_final(self) -> bool:
        """
        Verifica si es un estado final (no cambiará más).

        Returns:
            bool: True si está REJECTED, CANCELLED o WITHDRAWN
        """
        return self in {
            EnrollmentStatus.REJECTED,
            EnrollmentStatus.CANCELLED,
            EnrollmentStatus.WITHDRAWN,
        }

    def can_transition_to(self, new_status: "EnrollmentStatus") -> bool:
        """
        Verifica si es válida la transición al nuevo estado.

        Args:
            new_status: Estado destino

        Returns:
            bool: True si la transición es válida

        Ejemplos:
            >>> EnrollmentStatus.REQUESTED.can_transition_to(EnrollmentStatus.APPROVED)
            True
            >>> EnrollmentStatus.WITHDRAWN.can_transition_to(EnrollmentStatus.APPROVED)
            False
        """
        valid_transitions = {
            EnrollmentStatus.REQUESTED: {
                EnrollmentStatus.APPROVED,  # Creador aprueba
                EnrollmentStatus.REJECTED,  # Creador rechaza
                EnrollmentStatus.CANCELLED,  # Jugador cancela su solicitud
            },
            EnrollmentStatus.INVITED: {
                EnrollmentStatus.APPROVED,  # Jugador acepta invitación
                EnrollmentStatus.REJECTED,  # Creador retira invitación
                EnrollmentStatus.CANCELLED,  # Jugador declina invitación
            },
            EnrollmentStatus.APPROVED: {
                EnrollmentStatus.WITHDRAWN  # Jugador se retira
            },
            EnrollmentStatus.REJECTED: set(),  # Estado final
            EnrollmentStatus.CANCELLED: set(),  # Estado final
            EnrollmentStatus.WITHDRAWN: set(),  # Estado final
        }

        return new_status in valid_transitions.get(self, set())

    def __composite_values__(self):
        """
        Método requerido por SQLAlchemy composite().

        Returns:
            tuple: Valores para persistir en la base de datos
        """
        return (self.value,)
