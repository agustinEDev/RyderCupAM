"""
SQLAlchemy Refresh Token Repository.

Implementación del repositorio de Refresh Tokens usando SQLAlchemy (async).
"""

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from src.modules.user.domain.value_objects.refresh_token_id import RefreshTokenId
from src.modules.user.domain.value_objects.token_hash import TokenHash
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.sqlalchemy.refresh_token_mapper import (
    refresh_tokens_table,
)


class SQLAlchemyRefreshTokenRepository(RefreshTokenRepositoryInterface):
    """
    Implementación SQLAlchemy del repositorio de Refresh Tokens.

    Usa async/await para operaciones no bloqueantes.
    Sigue el patrón Repository de Clean Architecture.
    """

    def __init__(self, session: AsyncSession):
        """
        Inicializa el repositorio con una sesión de SQLAlchemy.

        Args:
            session: Sesión async de SQLAlchemy
        """
        self._session = session

    async def save(self, refresh_token: RefreshToken) -> RefreshToken:
        """
        Persiste un refresh token.

        Args:
            refresh_token: Entidad RefreshToken a persistir

        Returns:
            La entidad persistida
        """
        self._session.add(refresh_token)
        await self._session.flush()
        return refresh_token

    async def find_by_id(self, token_id: RefreshTokenId) -> RefreshToken | None:
        """
        Busca un refresh token por su ID.

        Args:
            token_id: ID del refresh token

        Returns:
            RefreshToken si existe, None si no se encuentra
        """
        stmt = select(RefreshToken).where(refresh_tokens_table.c.id == str(token_id.value))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_token_hash(self, token: str) -> RefreshToken | None:
        """
        Busca un refresh token por su hash.

        Hashea el token proporcionado y busca en BD.

        Args:
            token: Token JWT en texto plano

        Returns:
            RefreshToken si existe y el hash coincide, None si no
        """
        try:
            # Hashear el token para buscar en BD
            token_hash = TokenHash.from_token(token)

            stmt = select(RefreshToken).where(refresh_tokens_table.c.token_hash == token_hash.value)
            result = await self._session.execute(stmt)
            return result.scalar_one_or_none()
        except ValueError:
            # Token inválido, no puede hashearse
            return None

    async def find_all_by_user(self, user_id: UserId) -> list[RefreshToken]:
        """
        Busca todos los refresh tokens de un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            Lista de RefreshTokens (puede estar vacía)
        """
        stmt = (
            select(RefreshToken)
            .where(refresh_tokens_table.c.user_id == str(user_id.value))
            .order_by(refresh_tokens_table.c.created_at.desc())
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_all_for_user(self, user_id: UserId) -> int:
        """
        Revoca todos los refresh tokens de un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            Número de tokens revocados
        """
        stmt = (
            update(refresh_tokens_table)
            .where(
                refresh_tokens_table.c.user_id == str(user_id.value),
                refresh_tokens_table.c.revoked == False,  # noqa: E712
            )
            .values(revoked=True, revoked_at=datetime.now())
        )

        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0

    async def delete_expired(self) -> int:
        """
        Elimina todos los refresh tokens expirados de la base de datos.

        Returns:
            Número de tokens eliminados
        """
        stmt = delete(refresh_tokens_table).where(
            refresh_tokens_table.c.expires_at < datetime.now()
        )

        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0

    async def count_active_for_user(self, user_id: UserId) -> int:
        """
        Cuenta los refresh tokens activos de un usuario.

        Un token es activo si no está revocado y no ha expirado.

        Args:
            user_id: ID del usuario

        Returns:
            Número de tokens activos
        """
        stmt = (
            select(func.count())
            .select_from(refresh_tokens_table)
            .where(
                refresh_tokens_table.c.user_id == str(user_id.value),
                refresh_tokens_table.c.revoked == False,  # noqa: E712
                refresh_tokens_table.c.expires_at > datetime.now(),
            )
        )

        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def delete(self, token_id: RefreshTokenId) -> bool:
        """
        Elimina un refresh token específico.

        Args:
            token_id: ID del token a eliminar

        Returns:
            True si se eliminó, False si no existía
        """
        stmt = delete(refresh_tokens_table).where(refresh_tokens_table.c.id == str(token_id.value))

        result = await self._session.execute(stmt)
        await self._session.flush()
        return (result.rowcount or 0) > 0

    async def revoke_all_for_device(self, device_id: UserDeviceId) -> int:
        """
        Revoca todos los refresh tokens de un dispositivo específico.

        Este método es CRÍTICO para cerrar sesiones al revocar un dispositivo.
        Marca todos los tokens asociados al device_id como revocados.

        Args:
            device_id: ID del dispositivo cuyos tokens se revocarán

        Returns:
            Número de tokens revocados
        """
        stmt = (
            update(refresh_tokens_table)
            .where(
                refresh_tokens_table.c.device_id == str(device_id.value),
                refresh_tokens_table.c.revoked == False,  # noqa: E712 - Solo revocar los no revocados
            )
            .values(
                revoked=True,
                revoked_at=datetime.now(),
            )
        )

        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0
