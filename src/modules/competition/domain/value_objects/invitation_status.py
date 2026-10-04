"""
InvitationStatus Value Object - Estado de una invitacion a una competicion.

Define los estados posibles de una invitacion enviada por el creador.
"""

from enum import StrEnum


class InvitationStatus(StrEnum):
    """
    Enum para los estados de una invitacion.

    Estados:
    - PENDING: Invitacion enviada, pendiente de respuesta
    - ACCEPTED: Invitacion aceptada por el invitado
    - DECLINED: Invitacion rechazada por el invitado
    - EXPIRED: Invitacion expirada (pasaron 7 dias sin respuesta)

    State Machine:
      PENDING -> ACCEPTED (invitado acepta)
              -> DECLINED (invitado rechaza)
              -> EXPIRED  (pasan 7 dias)
              -> NO_ROOM  (se cerro la inscripcion o se lleno: no quedan plazas, #710, BE #359)
              -> CANCELLED (el organizador, quien la envio o un admin la retira, BE #359)
      ACCEPTED, DECLINED, EXPIRED, NO_ROOM y CANCELLED son estados terminales.
    """

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    # Decidido el 24 sep (#710): al cerrar la inscripcion, las pendientes se
    # rechazan por falta de plazas. Aceptar una despues metia a alguien con el
    # draft hecho y descuadraba los partidos
    NO_ROOM = "NO_ROOM"
    # La retiro quien invita (BE #359). Distinto de DECLINED: «el invitado dijo
    # que no» y «el organizador la retiro» no son lo mismo al leer la historia
    CANCELLED = "CANCELLED"

    def is_pending(self) -> bool:
        """Verifica si la invitacion esta pendiente de respuesta."""
        return self == InvitationStatus.PENDING

    def is_final(self) -> bool:
        """Verifica si es un estado final (no cambiara mas)."""
        return self in {
            InvitationStatus.ACCEPTED,
            InvitationStatus.DECLINED,
            InvitationStatus.EXPIRED,
            InvitationStatus.NO_ROOM,
            InvitationStatus.CANCELLED,
        }

    def can_transition_to(self, new_status: "InvitationStatus") -> bool:
        """
        Verifica si es valida la transicion al nuevo estado.

        Solo PENDING puede transicionar, a ACCEPTED, DECLINED, EXPIRED, NO_ROOM o CANCELLED.
        """
        valid_transitions = {
            InvitationStatus.PENDING: {
                InvitationStatus.ACCEPTED,
                InvitationStatus.DECLINED,
                InvitationStatus.EXPIRED,
                InvitationStatus.NO_ROOM,
                InvitationStatus.CANCELLED,
            },
            InvitationStatus.ACCEPTED: set(),
            InvitationStatus.DECLINED: set(),
            InvitationStatus.EXPIRED: set(),
            InvitationStatus.NO_ROOM: set(),
            InvitationStatus.CANCELLED: set(),
        }

        return new_status in valid_transitions.get(self, set())
