"""
Friendship Entity - Representa una relacion de amistad entre dos usuarios.

Esta entidad gestiona el ciclo de vida de una solicitud/relacion de amistad.
"""

from datetime import datetime

from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.utc_clock import utc_now

from ..exceptions.social_violations import (
    InvalidFriendshipStatusViolation,
    SelfFriendRequestViolation,
)
from ..value_objects.friendship_id import FriendshipId
from ..value_objects.friendship_status import FriendshipStatus


class Friendship:
    """
    Entidad Friendship - Representa una relacion de amistad entre dos usuarios.

    Gestiona:
    - Envio de solicitudes de amistad
    - Respuesta (aceptar/rechazar)
    - Bloqueo

    Invariantes:
    - requester_id y addressee_id no pueden ser None
    - Solo PENDING permite aceptar/rechazar
    - Solo PENDING o ACCEPTED permiten bloquear
    """

    def __init__(
        self,
        id: FriendshipId,
        requester_id: UserId,
        addressee_id: UserId,
        status: FriendshipStatus,
        blocked_by: UserId | None = None,
        responded_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        second_blocked_at: datetime | None = None,
    ):
        self._id = id
        self._requester_id = requester_id
        self._addressee_id = addressee_id
        self._status = status
        self._blocked_by = blocked_by
        self._responded_at = responded_at
        self._created_at = created_at or utc_now()
        self._updated_at = updated_at or utc_now()
        # Bloqueo de los dos (SB-02): cuándo bloqueó el participante que NO es
        # `blocked_by`, que ya le había bloqueado a él. None: solo bloquea uno
        self._second_blocked_at = second_blocked_at

    # ===========================================
    # FACTORY METHODS
    # ===========================================

    @classmethod
    def create(
        cls,
        id: FriendshipId,
        requester_id: UserId,
        addressee_id: UserId,
    ) -> "Friendship":
        """Factory method para crear una nueva solicitud de amistad con status PENDING."""
        if requester_id == addressee_id:
            raise SelfFriendRequestViolation("No puedes enviarte una solicitud a ti mismo.")

        now = utc_now()
        friendship = cls(
            id=id,
            requester_id=requester_id,
            addressee_id=addressee_id,
            status=FriendshipStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        return friendship

    @classmethod
    def create_blocked(
        cls,
        id: FriendshipId,
        blocker_id: UserId,
        blocked_id: UserId,
    ) -> "Friendship":
        """
        Factory method para bloquear directamente a un usuario sin amistad previa.

        El bloqueador queda registrado como `requester_id` por convencion de
        almacenamiento, pero la autoridad real sobre quien bloqueo se guarda en
        `blocked_by`.
        """
        if blocker_id == blocked_id:
            raise SelfFriendRequestViolation("No puedes bloquearte a ti mismo.")

        now = utc_now()
        friendship = cls(
            id=id,
            requester_id=blocker_id,
            addressee_id=blocked_id,
            status=FriendshipStatus.BLOCKED,
            blocked_by=blocker_id,
            responded_at=now,
            created_at=now,
            updated_at=now,
        )

        return friendship

    @classmethod
    def reconstruct(
        cls,
        id: FriendshipId,
        requester_id: UserId,
        addressee_id: UserId,
        status: FriendshipStatus,
        blocked_by: UserId | None = None,
        responded_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        second_blocked_at: datetime | None = None,
    ) -> "Friendship":
        """Reconstruye una amistad desde la base de datos."""
        return cls(
            id=id,
            requester_id=requester_id,
            addressee_id=addressee_id,
            status=status,
            blocked_by=blocked_by,
            responded_at=responded_at,
            created_at=created_at,
            updated_at=updated_at,
            second_blocked_at=second_blocked_at,
        )

    # ===========================================
    # PROPERTIES (Encapsulacion — solo lectura)
    # ===========================================

    @property
    def id(self) -> FriendshipId:
        return self._id

    @property
    def requester_id(self) -> UserId:
        return self._requester_id

    @property
    def addressee_id(self) -> UserId:
        return self._addressee_id

    @property
    def status(self) -> FriendshipStatus:
        return self._status

    @property
    def blocked_by(self) -> UserId | None:
        return self._blocked_by

    @property
    def second_blocked_at(self) -> datetime | None:
        """Cuándo bloqueó el otro participante, si también bloqueó (SB-02)."""
        return self._second_blocked_at

    @property
    def responded_at(self) -> datetime | None:
        return self._responded_at

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ===========================================
    # METODOS DE CONSULTA (QUERIES)
    # ===========================================

    def is_pending(self) -> bool:
        return self._status.is_pending()

    def is_accepted(self) -> bool:
        return self._status.is_accepted()

    def is_blocked(self) -> bool:
        return self._status.is_blocked()

    def bloqueado_por(self, user_id: UserId) -> bool:
        """
        Si `user_id` tiene puesto un bloqueo en esta fila (F-09): el primero
        (`blocked_by`) o el segundo, si los dos se bloquearon (SB-02). Un bloqueo
        sin autor (`blocked_by` NULL, que la tabla admite) no lo puso nadie.
        """
        if not self.is_blocked() or self._blocked_by is None:
            return False
        return self._blocked_by == user_id or self.segundo_bloqueador() == user_id

    def segundo_bloqueador(self) -> UserId | None:
        """Quien bloqueó al que ya le había bloqueado, o None si solo bloquea uno (SB-02)."""
        if not self.is_blocked() or self._blocked_by is None or self._second_blocked_at is None:
            return None
        return self.other_user_id(self._blocked_by)

    def segundo_bloqueo_de(self, user_id: UserId) -> datetime | None:
        """Cuándo bloqueó `user_id`, si su bloqueo es el segundo; si no, None (SB-02)."""
        return self._second_blocked_at if self.segundo_bloqueador() == user_id else None

    def lo_oculta_a(self, viewer_id: UserId) -> bool:
        """
        Si para `viewer_id` el otro no existe (F-09): el otro le bloqueó y él no
        bloqueó al otro. Si se bloquearon los dos, ninguno desaparece para el otro:
        si desapareciera, sabría que el otro también le bloqueó (SB-02).
        """
        if not self.involves_user(viewer_id):
            return False
        return self.bloqueado_por(self.other_user_id(viewer_id)) and not self.bloqueado_por(
            viewer_id
        )

    def involves_user(self, user_id: UserId) -> bool:
        """Verifica si el usuario dado participa en esta relacion (requester o addressee)."""
        return user_id in (self._requester_id, self._addressee_id)

    def other_user_id(self, user_id: UserId) -> UserId:
        """Devuelve el ID del otro usuario de la relacion, dado uno de los dos participantes."""
        if self._requester_id == user_id:
            return self._addressee_id
        if self._addressee_id == user_id:
            return self._requester_id
        raise ValueError("El usuario indicado no participa en esta relacion de amistad.")

    # ===========================================
    # METODOS DE COMANDO (CAMBIOS DE ESTADO)
    # ===========================================

    def accept(self) -> None:
        """Acepta la solicitud de amistad (PENDING -> ACCEPTED)."""
        if not self._status.can_transition_to(FriendshipStatus.ACCEPTED):
            raise InvalidFriendshipStatusViolation(
                f"Cannot accept friendship request in status {self._status.value}."
            )

        now = utc_now()
        self._status = FriendshipStatus.ACCEPTED
        self._responded_at = now
        self._updated_at = now

    def decline(self) -> None:
        """Rechaza la solicitud de amistad (PENDING -> DECLINED)."""
        if not self._status.can_transition_to(FriendshipStatus.DECLINED):
            raise InvalidFriendshipStatusViolation(
                f"Cannot decline friendship request in status {self._status.value}."
            )

        now = utc_now()
        self._status = FriendshipStatus.DECLINED
        self._responded_at = now
        self._updated_at = now

    def block(self, blocker_id: UserId) -> None:
        """
        Bloquea la relacion (PENDING/ACCEPTED -> BLOCKED).

        Sobre una fila ya bloqueada (SB-02): si el bloqueo ya es suyo, nada; si es
        del otro, se apunta el suyo como segundo sin tocar nada de lo que ve el
        otro (ni autor, ni fechas); si no tiene autor, pasa a ser suyo.
        """
        if self.is_blocked():
            self._bloquea_tambien(blocker_id)
            return
        if not self._status.can_transition_to(FriendshipStatus.BLOCKED):
            raise InvalidFriendshipStatusViolation(
                f"Cannot block friendship in status {self._status.value}."
            )

        now = utc_now()
        self._status = FriendshipStatus.BLOCKED
        self._blocked_by = blocker_id
        self._responded_at = now
        self._updated_at = now

    def _bloquea_tambien(self, blocker_id: UserId) -> None:
        """El bloqueo de `blocker_id` sobre una fila que ya estaba bloqueada."""
        if not self.involves_user(blocker_id):
            raise InvalidFriendshipStatusViolation("Only a participant can block.")
        if self.bloqueado_por(blocker_id):
            return
        if self._blocked_by is None:
            self._blocked_by = blocker_id
            return
        self._second_blocked_at = utc_now()

    def unblock(self, user_id: UserId) -> bool:
        """
        Quita el bloqueo de `user_id` (SB-02).

        Returns:
            True si con eso no queda ningún bloqueo y la fila se borra; False si
            queda el bloqueo del otro, que pasa a ser el único (`blocked_by`).

        Raises:
            InvalidFriendshipStatusViolation: Si `user_id` no tiene puesto un bloqueo
        """
        if not self.bloqueado_por(user_id):
            raise InvalidFriendshipStatusViolation("Only who blocked can unblock.")
        if self._second_blocked_at is None:
            return True
        if self._blocked_by == user_id:
            # Se va el primero: la fila pasa a ser del segundo, tal como él la veía
            # desde que bloqueó (él, el otro y la hora de su bloqueo), para que nada
            # de lo que le responda después delate el bloqueo que había antes
            queda = self.other_user_id(user_id)
            self._requester_id, self._addressee_id = queda, user_id
            self._blocked_by = queda
            self._created_at = self._updated_at = self._responded_at = self._second_blocked_at
        self._second_blocked_at = None
        return False

    # ===========================================
    # METODOS ESPECIALES
    # ===========================================

    def __str__(self) -> str:
        return f"Friendship({self._requester_id} -> {self._addressee_id}, {self._status.value})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Friendship) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
