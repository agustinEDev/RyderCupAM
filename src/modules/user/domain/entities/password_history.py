"""
Password History Entity - Domain Layer

Representa un registro de historial de contraseñas para prevenir reutilización.
"""

from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent

from ..events.password_history_recorded_event import PasswordHistoryRecordedEvent
from ..value_objects.password_history_id import PasswordHistoryId
from ..value_objects.user_id import UserId


class PasswordHistory:
    """
    Entidad PasswordHistory - Registro de una contraseña usada anteriormente.

    Esta entidad guarda hashes de contraseñas previas para prevenir que los usuarios
    reutilicen contraseñas recientes (últimas 5), mejorando la seguridad según OWASP A07.

    Security (OWASP A07):
        - Previene reutilización de contraseñas
        - Hashes almacenados con bcrypt (no texto plano)
        - Limpieza automática después de 1 año
        - Solo guarda últimas 5 contraseñas activas

    Attributes:
        id (PasswordHistoryId): Identificador único del registro
        user_id (UserId): Referencia al usuario
        password_hash (str): Hash bcrypt de la contraseña
        created_at (datetime): Timestamp de cuándo se guardó
    """

    def __init__(
        self,
        id: PasswordHistoryId | None,
        user_id: UserId,
        password_hash: str,
        created_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        """
        Inicializa un registro de historial de contraseñas.

        Args:
            id: Identificador único (None para auto-generar)
            user_id: ID del usuario dueño del historial
            password_hash: Hash bcrypt de la contraseña
            created_at: Timestamp de creación (None para NOW())
            domain_events: Eventos de dominio pendientes
        """
        self.id = id or PasswordHistoryId.generate()
        self.user_id = user_id
        self.password_hash = password_hash
        self.created_at = created_at or datetime.now()
        self._domain_events = domain_events or []

    @classmethod
    def create(
        cls, user_id: UserId, password_hash: str, total_history_count: int = 1
    ) -> "PasswordHistory":
        """
        Factory method para crear un nuevo registro de historial.

        Args:
            user_id: ID del usuario
            password_hash: Hash bcrypt de la contraseña
            total_history_count: Total de registros en historial después del cambio

        Returns:
            PasswordHistory: Nueva instancia con ID generado

        Example:
            >>> user_id = UserId.generate()
            >>> history = PasswordHistory.create(
            ...     user_id=user_id,
            ...     password_hash="$2b$12$...",
            ...     total_history_count=3
            ... )
            >>> history.id is not None
            True
        """
        history = cls(
            id=PasswordHistoryId.generate(),
            user_id=user_id,
            password_hash=password_hash,
            created_at=datetime.now(),
        )

        # Emitir evento de dominio
        history._add_domain_event(
            PasswordHistoryRecordedEvent(
                user_id=str(user_id.value),
                history_id=str(history.id.value),
                recorded_at=history.created_at,
                total_history_count=total_history_count,
            )
        )

        return history

    def is_older_than(self, days: int) -> bool:
        """
        Verifica si el registro es más antiguo que N días.

        Args:
            days: Número de días para comparar

        Returns:
            bool: True si el registro es más antiguo que N días

        Example:
            >>> history.created_at = datetime.now() - timedelta(days=400)
            >>> history.is_older_than(365)
            True
        """
        now = datetime.now()
        age = (now - self.created_at).days
        return age > days

    # === Métodos para manejo de eventos de dominio ===

    def _add_domain_event(self, event: DomainEvent) -> None:
        """Agrega un evento de dominio a la colección interna."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        self._domain_events.append(event)

    def get_domain_events(self) -> list[DomainEvent]:
        """Obtiene una copia de todos los eventos de dominio pendientes."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        """Limpia todos los eventos de dominio de la colección."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        self._domain_events.clear()

    def has_domain_events(self) -> bool:
        """Verifica si la entidad tiene eventos de dominio pendientes."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        return len(self._domain_events) > 0

    def __str__(self) -> str:
        """Representación string del historial (sin mostrar hash completo)."""
        return (
            f"PasswordHistory(id={self.id}, user_id={self.user_id}, created_at={self.created_at})"
        )

    def __repr__(self) -> str:
        """Representación para debugging."""
        return self.__str__()
