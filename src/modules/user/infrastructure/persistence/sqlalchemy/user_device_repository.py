# src/modules/user/infrastructure/persistence/sqlalchemy/user_device_repository.py
"""
User Device Repository - Infrastructure Layer

Implementación SQLAlchemy del repositorio de dispositivos de usuario.
Maneja persistencia async de dispositivos en PostgreSQL.

Responsabilidades:
- CRUD de dispositivos (save, find, revoke)
- Queries optimizadas con índices
- Reconstrucción de UserDevice desde BD con DeviceFingerprint
- Manejo de errores de persistencia

Patrón: Repository Pattern + Async SQLAlchemy
"""


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.repositories.user_device_repository_interface import (
    UserDeviceRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


class SQLAlchemyUserDeviceRepository(UserDeviceRepositoryInterface):
    """
    Implementación SQLAlchemy del repositorio de dispositivos de usuario.

    Características:
    - Async/await con AsyncSession
    - Reconstrucción de entidades con DeviceFingerprint desde columnas BD
    - Queries optimizadas con índices (ix_user_devices_user_id)
    - Manejo automático de TypeDecorators (UserDeviceId, UserId)

    Diferencia clave vs UserRepository:
    - DeviceFingerprint NO se mapea con composite() porque:
      1. Tiene 4 campos (device_name, user_agent, ip_address, fingerprint_hash)
      2. Contiene lógica de validación (generate_hash()) en constructor
      3. Se reconstruye manualmente con reconstitute() al leer de BD

    Examples:
        >>> # Guardar dispositivo nuevo
        >>> device = UserDevice.create(user_id, fingerprint)
        >>> await repo.save(device)

        >>> # Buscar dispositivo conocido
        >>> existing = await repo.find_by_user_and_fingerprint(
        ...     user_id, fingerprint.fingerprint_hash
        ... )
        >>> if existing:
        ...     existing.update_last_used()
        ...     await repo.save(existing)
    """

    def __init__(self, session: AsyncSession):
        """
        Inicializa el repositorio con una sesión async de SQLAlchemy.

        Args:
            session: AsyncSession activa (generalmente desde UoW)
        """
        self._session = session

    async def save(self, device: UserDevice) -> None:
        """
        Persiste un dispositivo en la base de datos.

        Maneja tanto INSERT (dispositivo nuevo) como UPDATE (existente).
        SQLAlchemy detecta automáticamente si el objeto está en la sesión.

        Args:
            device: UserDevice a persistir

        Note:
            - Los eventos de dominio del dispositivo NO se procesan aquí
            - Esa responsabilidad es del UoW en commit()
            - El mapper convierte automáticamente DeviceFingerprint → columnas
        """
        self._session.add(device)

    async def find_by_id(self, device_id: UserDeviceId) -> UserDevice | None:
        """
        Busca un dispositivo por su ID.

        Args:
            device_id: UserDeviceId del dispositivo

        Returns:
            Optional[UserDevice]: Dispositivo si existe, None en caso contrario

        Note:
            - Usa session.get() que es más rápido que query
            - Aprovecha caché de identidad de SQLAlchemy
        """
        return await self._session.get(UserDevice, device_id)

    async def find_by_user_and_fingerprint(
        self, user_id: UserId, fingerprint_hash: str
    ) -> UserDevice | None:
        """
        Busca un dispositivo ACTIVO por usuario y hash de fingerprint.

        Este es el query crítico para detectar dispositivos conocidos.
        Usa el índice único parcial ix_user_devices_unique_active_fingerprint.

        Args:
            user_id: UserId del propietario
            fingerprint_hash: Hash SHA256 del DeviceFingerprint

        Returns:
            Optional[UserDevice]: Dispositivo activo si existe, None en caso contrario

        Note:
            - Solo busca dispositivos con is_active=True
            - Aprovecha índice único parcial para búsqueda rápida
            - Usa atributos privados (_user_id, _fingerprint_hash) del mapper
        """
        statement = (
            select(UserDevice)
            .where(UserDevice._user_id == user_id)
            .where(UserDevice._fingerprint_hash == fingerprint_hash)
            .where(UserDevice._is_active == True)  # noqa: E712
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_active_by_user(self, user_id: UserId) -> list[UserDevice]:
        """
        Lista todos los dispositivos ACTIVOS de un usuario.

        Retorna dispositivos ordenados por last_used_at descendente
        (más recientes primero).

        Args:
            user_id: UserId del propietario

        Returns:
            List[UserDevice]: Lista de dispositivos activos (vacía si no hay)

        Note:
            - Usa índice ix_user_devices_user_id para búsqueda rápida
            - Solo dispositivos con is_active=True
            - Order by last_used_at DESC para mejor UX
        """
        statement = (
            select(UserDevice)
            .where(UserDevice._user_id == user_id)
            .where(UserDevice._is_active == True)  # noqa: E712
            .order_by(UserDevice._last_used_at.desc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def revoke(self, device_id: UserDeviceId) -> None:
        """
        Revoca un dispositivo (marca como inactivo).

        Implementación eficiente: busca dispositivo y llama a device.revoke()
        en lugar de UPDATE directo en BD (mantiene lógica en Domain Layer).

        Args:
            device_id: UserDeviceId del dispositivo a revocar

        Raises:
            ValueError: Si el dispositivo no existe
            RuntimeError: Si el dispositivo ya estaba revocado

        Note:
            - NO hace commit (responsabilidad del UoW)
            - Lanza eventos de dominio (DeviceRevokedEvent)
            - El save() se hace implícitamente al estar en la sesión
        """
        device = await self.find_by_id(device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")

        device.revoke()
        # No necesitamos save() explícito: el objeto ya está en la sesión
        # y SQLAlchemy detectará los cambios al commit
