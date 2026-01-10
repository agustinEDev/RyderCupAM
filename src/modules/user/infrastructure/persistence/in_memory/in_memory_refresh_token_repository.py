"""
In-Memory Refresh Token Repository for Testing.

Implementación en memoria del repositorio de refresh tokens para tests unitarios.
"""

from datetime import datetime

from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from src.modules.user.domain.value_objects.refresh_token_id import RefreshTokenId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.security.token_hash import hash_token


class InMemoryRefreshTokenRepository(RefreshTokenRepositoryInterface):
    """
    Repositorio en memoria para RefreshToken (usado en tests).

    Almacena los tokens en un diccionario en memoria para tests rápidos
    sin necesidad de base de datos real.
    """

    def __init__(self):
        """Inicializa el repositorio con almacenamiento vacío."""
        self._tokens: dict[str, RefreshToken] = {}  # Key: token_id (str)

    async def save(self, refresh_token: RefreshToken) -> RefreshToken:
        """
        Guarda un refresh token en memoria.

        Args:
            refresh_token: Token a guardar

        Returns:
            El token guardado
        """
        token_id = str(refresh_token.id.value)
        self._tokens[token_id] = refresh_token
        return refresh_token

    async def find_by_id(self, token_id: RefreshTokenId) -> RefreshToken | None:
        """
        Busca un token por su ID.

        Args:
            token_id: ID del token

        Returns:
            RefreshToken si existe, None si no
        """
        return self._tokens.get(str(token_id.value))

    async def find_by_token_hash(self, token: str) -> RefreshToken | None:
        """
        Busca un token por su hash.

        Args:
            token: Token JWT en texto plano

        Returns:
            RefreshToken si existe, None si no
        """
        token_hash_value = hash_token(token)

        for refresh_token in self._tokens.values():
            if refresh_token.token_hash.value == token_hash_value:
                return refresh_token

        return None

    async def find_all_by_user(self, user_id: UserId) -> list[RefreshToken]:
        """
        Busca todos los tokens de un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            Lista de RefreshTokens
        """
        return [
            token
            for token in self._tokens.values()
            if token.user_id.value == user_id.value
        ]

    async def revoke_all_for_user(self, user_id: UserId) -> int:
        """
        Revoca todos los tokens de un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            Número de tokens revocados
        """
        count = 0
        for token in self._tokens.values():
            if token.user_id.value == user_id.value and not token.revoked:
                token.revoke()
                count += 1
        return count

    async def delete_expired(self) -> int:
        """
        Elimina todos los tokens expirados.

        Returns:
            Número de tokens eliminados
        """
        expired_ids = [
            token_id for token_id, token in self._tokens.items() if token.is_expired()
        ]

        for token_id in expired_ids:
            del self._tokens[token_id]

        return len(expired_ids)

    async def count_active_for_user(self, user_id: UserId) -> int:
        """
        Cuenta los tokens activos de un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            Número de tokens activos (no revocados, no expirados)
        """
        now = datetime.now()
        return sum(
            1
            for token in self._tokens.values()
            if token.user_id.value == user_id.value
            and not token.revoked
            and token.expires_at > now
        )

    async def delete(self, token_id: RefreshTokenId) -> bool:
        """
        Elimina un token específico.

        Args:
            token_id: ID del token a eliminar

        Returns:
            True si se eliminó, False si no existía
        """
        token_id_str = str(token_id.value)
        if token_id_str in self._tokens:
            del self._tokens[token_id_str]
            return True
        return False
