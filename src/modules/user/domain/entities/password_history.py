"""
Password History Entity - Domain Layer

Representa un registro de historial de contraseñas para prevenir reutilización.
"""

from datetime import datetime

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
    ):
        """
        Inicializa un registro de historial de contraseñas.

        Args:
            id: Identificador único (None para auto-generar)
            user_id: ID del usuario dueño del historial
            password_hash: Hash bcrypt de la contraseña
            created_at: Timestamp de creación (None para NOW())
        """
        self._id = id or PasswordHistoryId.generate()
        self._user_id = user_id
        self._password_hash = password_hash
        self._created_at = created_at or datetime.now()

    # ===========================================
    # PROPERTIES (Encapsulación — solo lectura)
    # ===========================================

    @property
    def id(self) -> PasswordHistoryId:
        return self._id

    @property
    def user_id(self) -> UserId:
        return self._user_id

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @classmethod
    def create(cls, user_id: UserId, password_hash: str) -> "PasswordHistory":
        """
        Factory method para crear un nuevo registro de historial.

        Args:
            user_id: ID del usuario
            password_hash: Hash bcrypt de la contraseña

        Returns:
            PasswordHistory: Nueva instancia con ID generado

        Example:
            >>> user_id = UserId.generate()
            >>> history = PasswordHistory.create(
            ...     user_id=user_id,
            ...     password_hash="$2b$12$...",
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

        return history

    def is_older_than(self, days: int) -> bool:
        """
        Verifica si el registro es más antiguo que N días.

        Args:
            days: Número de días para comparar

        Returns:
            bool: True si el registro es más antiguo que N días

        Example:
            >>> # Asumiendo un registro creado hace 400 días
            >>> history.is_older_than(365)
            True
        """
        now = datetime.now()
        age = (now - self.created_at).days
        return age > days

    def __str__(self) -> str:
        """Representación string del historial (sin mostrar hash completo)."""
        return (
            f"PasswordHistory(id={self.id}, user_id={self.user_id}, created_at={self.created_at})"
        )

    def __repr__(self) -> str:
        """Representación para debugging."""
        return self.__str__()
