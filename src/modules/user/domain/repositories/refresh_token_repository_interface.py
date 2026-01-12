"""
RefreshToken Repository Interface.

Define el contrato para persistencia de refresh tokens.
"""

from abc import ABC, abstractmethod

from src.modules.user.domain.entities.refresh_token import RefreshToken
from src.modules.user.domain.value_objects.refresh_token_id import RefreshTokenId
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


class RefreshTokenRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de Refresh Tokens.

    Define las operaciones de persistencia necesarias para gestionar
    tokens de renovación (refresh tokens) en la capa de dominio.

    Esta interfaz sigue el patrón Repository, permitiendo que el dominio
    no dependa de detalles de implementación (SQLAlchemy, Redis, etc.).
    """

    @abstractmethod
    async def save(self, refresh_token: RefreshToken) -> RefreshToken:
        """
        Persiste un refresh token.

        Guarda un nuevo refresh token o actualiza uno existente.

        Args:
            refresh_token: Entidad RefreshToken a persistir

        Returns:
            La entidad persistida

        Example:
            >>> token = RefreshToken.create(user_id, jwt_token)
            >>> saved = await repository.save(token)
        """
        pass

    @abstractmethod
    async def find_by_id(self, token_id: RefreshTokenId) -> RefreshToken | None:
        """
        Busca un refresh token por su ID.

        Args:
            token_id: ID del refresh token

        Returns:
            RefreshToken si existe, None si no se encuentra
        """
        pass

    @abstractmethod
    async def find_by_token_hash(self, token: str) -> RefreshToken | None:
        """
        Busca un refresh token por su hash.

        Este método recibe el token JWT en texto plano, lo hashea,
        y busca en la base de datos por el hash correspondiente.

        Args:
            token: Token JWT en texto plano

        Returns:
            RefreshToken si existe y el hash coincide, None si no

        Example:
            >>> token_jwt = "eyJhbGciOiJIUzI1NiIsInR5..."
            >>> refresh_token = await repository.find_by_token_hash(token_jwt)
            >>> if refresh_token and refresh_token.is_valid(token_jwt):
            >>>     # Token válido, renovar access token
        """
        pass

    @abstractmethod
    async def find_all_by_user(self, user_id: UserId) -> list[RefreshToken]:
        """
        Busca todos los refresh tokens de un usuario.

        Útil para:
        - Revocar todos los tokens en logout de todos los dispositivos
        - Ver sesiones activas del usuario
        - Auditoría de seguridad

        Args:
            user_id: ID del usuario

        Returns:
            Lista de RefreshTokens (puede estar vacía)

        Example:
            >>> tokens = await repository.find_all_by_user(user_id)
            >>> active_tokens = [t for t in tokens if not t.revoked and not t.is_expired()]
        """
        pass

    @abstractmethod
    async def revoke_all_for_user(self, user_id: UserId) -> int:
        """
        Revoca todos los refresh tokens de un usuario.

        Útil para:
        - Logout de todos los dispositivos
        - Cambio de contraseña (invalidar todas las sesiones)
        - Compromiso de cuenta detectado

        Args:
            user_id: ID del usuario

        Returns:
            Número de tokens revocados

        Example:
            >>> # Usuario cambia contraseña -> invalidar todas las sesiones
            >>> revoked_count = await repository.revoke_all_for_user(user_id)
        """
        pass

    @abstractmethod
    async def delete_expired(self) -> int:
        """
        Elimina todos los refresh tokens expirados de la base de datos.

        Método de limpieza que debe ejecutarse periódicamente
        (ej: tarea cron diaria) para liberar espacio en BD.

        Returns:
            Número de tokens eliminados

        Example:
            >>> # Ejecutar diariamente a las 3am
            >>> deleted = await repository.delete_expired()
            >>> logger.info(f"Cleaned up {deleted} expired refresh tokens")
        """
        pass

    @abstractmethod
    async def count_active_for_user(self, user_id: UserId) -> int:
        """
        Cuenta los refresh tokens activos (no revocados, no expirados) de un usuario.

        Útil para:
        - Limitar número de sesiones simultáneas
        - Dashboard de seguridad ("Tienes 3 sesiones activas")
        - Detección de uso anómalo

        Args:
            user_id: ID del usuario

        Returns:
            Número de tokens activos

        Example:
            >>> active_sessions = await repository.count_active_for_user(user_id)
            >>> if active_sessions > 10:
            >>>     # Posible compromiso de cuenta
            >>>     await send_security_alert(user_id)
        """
        pass

    @abstractmethod
    async def delete(self, token_id: RefreshTokenId) -> bool:
        """
        Elimina un refresh token específico.

        Args:
            token_id: ID del token a eliminar

        Returns:
            True si se eliminó, False si no existía

        Example:
            >>> deleted = await repository.delete(token_id)
        """
        pass

    @abstractmethod
    async def revoke_all_for_device(self, device_id: UserDeviceId) -> int:
        """
        Revoca todos los refresh tokens de un dispositivo específico.

        Este método es CRÍTICO para la funcionalidad de revocación de dispositivos.
        Cuando un usuario revoca un dispositivo, TODOS los refresh tokens asociados
        a ese dispositivo deben invalidarse para cerrar las sesiones activas.

        Útil para:
        - Revocar dispositivo → cerrar sesiones del dispositivo
        - Usuario revoca Safari iOS → Safari iOS se desloguea automáticamente
        - Compromiso de dispositivo detectado

        Args:
            device_id: ID del dispositivo cuyos tokens se revocarán

        Returns:
            Número de tokens revocados

        Example:
            >>> # Usuario revoca su iPhone desde su Mac
            >>> device_id = UserDeviceId("550e8400-...")
            >>> revoked_count = await repository.revoke_all_for_device(device_id)
            >>> # Todos los refresh tokens del iPhone quedan inválidos
            >>> # iPhone se desloguea al intentar refrescar el access token
        """
        pass
