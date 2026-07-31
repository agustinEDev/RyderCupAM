"""
FriendshipStatus Value Object - Estado de una relacion de amistad entre usuarios.

Define los estados posibles de una relacion de amistad.
"""

from enum import StrEnum


class FriendshipStatus(StrEnum):
    """
    Enum para los estados de una relacion de amistad.

    Estados:
    - PENDING: Solicitud enviada, pendiente de respuesta del destinatario
    - ACCEPTED: Solicitud aceptada, los usuarios son amigos
    - DECLINED: Solicitud rechazada por el destinatario
    - BLOCKED: Uno de los dos usuarios ha bloqueado al otro

    State Machine:
      PENDING -> ACCEPTED (addressee acepta)
              -> DECLINED (addressee rechaza)
              -> BLOCKED  (cualquiera de los dos bloquea)
      ACCEPTED -> BLOCKED (cualquiera de los dos bloquea a un amigo existente)
      DECLINED, BLOCKED son estados terminales (una nueva solicitud crea un registro nuevo).
    """

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    BLOCKED = "BLOCKED"

    def is_pending(self) -> bool:
        """Verifica si la solicitud esta pendiente de respuesta."""
        return self == FriendshipStatus.PENDING

    def is_accepted(self) -> bool:
        """Verifica si los usuarios son amigos."""
        return self == FriendshipStatus.ACCEPTED

    def is_blocked(self) -> bool:
        """Verifica si la relacion esta bloqueada."""
        return self == FriendshipStatus.BLOCKED

    def is_final(self) -> bool:
        """Verifica si es un estado final (no cambiara mas salvo eliminacion)."""
        return self in {FriendshipStatus.DECLINED, FriendshipStatus.BLOCKED}

    def can_transition_to(self, new_status: "FriendshipStatus") -> bool:
        """Verifica si es valida la transicion al nuevo estado."""
        valid_transitions = {
            FriendshipStatus.PENDING: {
                FriendshipStatus.ACCEPTED,
                FriendshipStatus.DECLINED,
                FriendshipStatus.BLOCKED,
            },
            FriendshipStatus.ACCEPTED: {FriendshipStatus.BLOCKED},
            FriendshipStatus.DECLINED: set(),
            FriendshipStatus.BLOCKED: set(),
        }

        return new_status in valid_transitions.get(self, set())
