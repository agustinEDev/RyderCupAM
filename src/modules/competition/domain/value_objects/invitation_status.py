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
              -> NO_ROOM  (se lleno, BE #359; o se cancelo, 15 nov 2026. Hasta el 15 nov
                           tambien al cerrar la inscripcion, #710: ahora espera, ON_HOLD)
              -> CANCELLED (el organizador, quien la envio o un admin la retira, BE #359)
              -> ON_HOLD  (se cerro la inscripcion: espera a que se reabra, 15 nov 2026)
      ON_HOLD -> PENDING (se reabre, con 7 dias nuevos), NO_ROOM (empieza, se cancela,
                 se llena o se reabre sin sitio), DECLINED o CANCELLED; esperando no
                 caduca (nunca EXPIRED) y no se acepta.
      ACCEPTED, DECLINED, EXPIRED, NO_ROOM y CANCELLED son estados terminales.
    """

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    # Sin plaza: se lleno (BE #359), o empezo o se cancelo sin que la aceptara
    # (15 nov 2026). Del 24 sep (#710) al 15 nov tambien al cerrar la inscripcion;
    # desde entonces, al cerrar, espera (ON_HOLD)
    NO_ROOM = "NO_ROOM"
    # La retiro quien invita (BE #359). Distinto de DECLINED: «el invitado dijo
    # que no» y «el organizador la retiro» no son lo mismo al leer la historia
    CANCELLED = "CANCELLED"
    # «En lista de espera: la inscripción está cerrada. Si el organizador la
    # reabre, podrás aceptarla» (Agustín, 15 nov 2026, P1). No es la lista de
    # espera de las franjas de un stroke play: esa es de inscripciones
    ON_HOLD = "ON_HOLD"

    def is_pending(self) -> bool:
        """Verifica si la invitacion esta pendiente de respuesta."""
        return self == InvitationStatus.PENDING

    def is_on_hold(self) -> bool:
        """Si espera a que se reabra la inscripcion (P1)."""
        return self == InvitationStatus.ON_HOLD

    def is_open(self) -> bool:
        """Si sigue viva: pendiente o en espera. Se puede rechazar y retirar."""
        return self in {InvitationStatus.PENDING, InvitationStatus.ON_HOLD}

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

        PENDING, a ACCEPTED, DECLINED, EXPIRED, NO_ROOM, CANCELLED u ON_HOLD; ON_HOLD,
        a PENDING, DECLINED, NO_ROOM o CANCELLED (ni ACCEPTED ni EXPIRED).
        """
        valid_transitions = {
            InvitationStatus.PENDING: {
                InvitationStatus.ACCEPTED,
                InvitationStatus.DECLINED,
                InvitationStatus.EXPIRED,
                InvitationStatus.NO_ROOM,
                InvitationStatus.CANCELLED,
                InvitationStatus.ON_HOLD,
            },
            InvitationStatus.ON_HOLD: {
                InvitationStatus.PENDING,
                InvitationStatus.DECLINED,
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
