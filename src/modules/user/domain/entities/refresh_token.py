"""
RefreshToken Entity.

Entidad que representa un token de renovación (refresh token) para autenticación.
"""

from datetime import datetime, timedelta

from src.modules.user.domain.value_objects.refresh_token_id import RefreshTokenId
from src.modules.user.domain.value_objects.token_hash import TokenHash
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


class RefreshToken:
    """
    Entidad de dominio RefreshToken.

    Representa un token de renovación que permite obtener nuevos access tokens
    sin necesidad de re-autenticarse con usuario/contraseña.

    Lifecycle:
    - Creado en login/register
    - Usado en /refresh-token para obtener nuevo access token
    - Revocado en logout o cambio de contraseña
    - Expirado después de 7 días (o configurado)

    Attributes:
        id: Identificador único del refresh token
        user_id: ID del usuario propietario
        device_id: ID del dispositivo asociado (permite revocar por dispositivo)
        token_hash: Hash SHA256 del token JWT (no almacenamos texto plano)
        expires_at: Fecha/hora de expiración
        created_at: Fecha/hora de creación
        revoked: Si el token ha sido revocado manualmente
        revoked_at: Fecha/hora de revocación (si aplica)
    """

    def __init__(
        self,
        id: RefreshTokenId,
        user_id: UserId,
        token_hash: TokenHash,
        expires_at: datetime,
        device_id: UserDeviceId | None = None,
        created_at: datetime | None = None,
        revoked: bool = False,
        revoked_at: datetime | None = None,
    ):
        """
        Inicializa un RefreshToken.

        Args:
            id: Identificador único del token
            user_id: ID del usuario propietario
            token_hash: Hash del token JWT
            expires_at: Fecha/hora de expiración
            device_id: ID del dispositivo asociado (opcional para backward compatibility)
            created_at: Fecha/hora de creación (auto-generado si None)
            revoked: Si el token está revocado
            revoked_at: Fecha/hora de revocación
        """
        self._id = id
        self._user_id = user_id
        self._token_hash = token_hash
        self._expires_at = expires_at
        self._device_id = device_id
        self._created_at = created_at or datetime.now()
        self._revoked = revoked
        self._revoked_at = revoked_at

    @property
    def id(self) -> RefreshTokenId:
        """Retorna el ID del refresh token."""
        return self._id

    @property
    def user_id(self) -> UserId:
        """Retorna el ID del usuario propietario."""
        return self._user_id

    @property
    def token_hash(self) -> TokenHash:
        """Retorna el hash del token."""
        return self._token_hash

    @property
    def expires_at(self) -> datetime:
        """Retorna la fecha de expiración."""
        return self._expires_at

    @property
    def created_at(self) -> datetime:
        """Retorna la fecha de creación."""
        return self._created_at

    @property
    def revoked(self) -> bool:
        """Retorna si el token está revocado."""
        return self._revoked

    @property
    def revoked_at(self) -> datetime | None:
        """Retorna la fecha de revocación (si aplica)."""
        return self._revoked_at

    @property
    def device_id(self) -> UserDeviceId | None:
        """Retorna el ID del dispositivo asociado."""
        return self._device_id

    @classmethod
    def create(
        cls,
        user_id: UserId,
        token: str,
        device_id: UserDeviceId | None = None,
        expires_in_days: int = 7,
    ) -> "RefreshToken":
        """
        Crea un nuevo RefreshToken.

        Factory method para crear tokens con valores por defecto.

        Args:
            user_id: ID del usuario propietario
            token: Token JWT en texto plano (se hasheará)
            device_id: ID del dispositivo asociado (requerido para revocación correcta)
            expires_in_days: Días hasta expiración (default 7)

        Returns:
            Nueva instancia de RefreshToken

        Example:
            >>> user_id = UserId.generate()
            >>> device_id = UserDeviceId.generate()
            >>> token_jwt = "eyJhbGciOiJIUzI1NiIsInR5..."
            >>> refresh_token = RefreshToken.create(user_id, token_jwt, device_id)
        """
        token_id = RefreshTokenId.generate()
        token_hash = TokenHash.from_token(token)
        expires_at = datetime.now() + timedelta(days=expires_in_days)

        return cls(
            id=token_id,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_id=device_id,
            created_at=datetime.now(),
            revoked=False,
            revoked_at=None,
        )

    def is_valid(self, token: str) -> bool:
        """
        Verifica si este refresh token es válido para uso.

        Un token es válido si:
        1. No está revocado
        2. No ha expirado
        3. El token proporcionado coincide con el hash almacenado

        Args:
            token: Token JWT en texto plano a verificar

        Returns:
            True si el token es válido y puede usarse
        """
        # 1. Verificar que no esté revocado
        if self._revoked:
            return False

        # 2. Verificar que no haya expirado
        if datetime.now() > self._expires_at:
            return False

        # 3. Verificar que el token coincida con el hash
        return self._token_hash.verify(token)

    def revoke(self) -> None:
        """
        Revoca este refresh token.

        Marca el token como revocado y establece la fecha de revocación.
        Llamado en logout o cambio de contraseña.

        Example:
            >>> refresh_token.revoke()
            >>> assert refresh_token.revoked is True
        """
        if not self._revoked:
            self._revoked = True
            self._revoked_at = datetime.now()

    def is_expired(self) -> bool:
        """
        Verifica si el token ha expirado.

        Returns:
            True si la fecha de expiración ha pasado
        """
        return datetime.now() > self._expires_at

    def __eq__(self, other: object) -> bool:
        """Compara dos RefreshTokens por ID."""
        if not isinstance(other, RefreshToken):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        """Hash del RefreshToken para usar en sets/dicts."""
        return hash(self._id)

    def __repr__(self) -> str:
        """Representación debug del RefreshToken."""
        if self._revoked:
            status = "revoked"
        elif self.is_expired():
            status = "expired"
        else:
            status = "valid"
        return f"RefreshToken(id={self._id}, user_id={self._user_id}, status={status})"
