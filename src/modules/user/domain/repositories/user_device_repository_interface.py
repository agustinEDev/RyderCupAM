"""
Interfaz del repositorio de dispositivos de usuario (Puerto en Hexagonal Architecture).

Este módulo define el contrato (interface) que debe implementar cualquier
repositorio de dispositivos, sin especificar CÓMO se implementa.

Responsabilidades:
- Definir operaciones de persistencia abstractas
- Servir como puerto (port) para el adaptador de infraestructura
- Permitir inversión de dependencias (Domain no depende de Infrastructure)
- Facilitar testing (mocks, in-memory repos)

Implementaciones:
- SQLAlchemyUserDeviceRepository (Infrastructure Layer) - Producción
- InMemoryUserDeviceRepository (Tests) - Testing unitario

Patrón: Repository Pattern + Dependency Inversion Principle (SOLID)
"""

from abc import ABC, abstractmethod

from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


class UserDeviceRepositoryInterface(ABC):
    """
    Interfaz (puerto) para el repositorio de dispositivos de usuario.

    Define el contrato que debe cumplir cualquier implementación de
    repositorio de dispositivos, independientemente de la tecnología
    de persistencia subyacente (PostgreSQL, MongoDB, in-memory, etc.).

    Esta interfaz vive en la Domain Layer y es implementada en la
    Infrastructure Layer, siguiendo el principio de Inversión de
    Dependencias (Dependency Inversion Principle).

    Métodos:
        save: Persiste un dispositivo (nuevo o actualizado)
        find_by_id: Busca un dispositivo por su ID
        find_by_user_and_fingerprint: Busca por usuario + fingerprint hash
        find_active_by_user: Lista dispositivos activos de un usuario
        revoke: Marca un dispositivo como inactivo

    Examples:
        >>> # En Use Case (Application Layer)
        >>> class DetectDeviceUseCase:
        ...     def __init__(self, repo: UserDeviceRepositoryInterface):
        ...         self._repo = repo  # ← Depende de interfaz, no implementación
        ...
        ...     async def execute(self, user_id, fingerprint):
        ...         device = await self._repo.find_by_user_and_fingerprint(...)
        ...         if not device:
        ...             new_device = UserDevice.create(user_id, fingerprint)
        ...             await self._repo.save(new_device)
    """

    @abstractmethod
    async def save(self, device: UserDevice) -> None:
        """
        Persiste un dispositivo en el almacenamiento.

        Este método maneja tanto dispositivos nuevos (INSERT) como
        actualizaciones de dispositivos existentes (UPDATE).

        Responsabilidades adicionales:
        - Procesar eventos de dominio del dispositivo
        - Hacer commit de la transacción (si usa UoW)
        - Manejar errores de persistencia

        Args:
            device: Entidad UserDevice a persistir

        Raises:
            RepositoryError: Si hay error en la persistencia
            DuplicateDeviceError: Si el fingerprint ya existe para ese usuario

        Examples:
            >>> # Guardar dispositivo nuevo
            >>> device = UserDevice.create(user_id, fingerprint)
            >>> await repo.save(device)

            >>> # Actualizar dispositivo existente
            >>> device = await repo.find_by_id(device_id)
            >>> device.update_last_used()
            >>> await repo.save(device)  # UPDATE
        """
        pass

    @abstractmethod
    async def find_by_id(self, device_id: UserDeviceId) -> UserDevice | None:
        """
        Busca un dispositivo por su ID.

        Args:
            device_id: ID del dispositivo a buscar

        Returns:
            Optional[UserDevice]: Dispositivo si existe, None si no se encuentra

        Examples:
            >>> device_id = UserDeviceId.from_string("550e8400-...")
            >>> device = await repo.find_by_id(device_id)
            >>> if device:
            ...     print(device.device_name)
            ... else:
            ...     print("Dispositivo no encontrado")
        """
        pass

    @abstractmethod
    async def find_by_user_and_fingerprint(
        self, user_id: UserId, fingerprint_hash: str
    ) -> UserDevice | None:
        """
        Busca un dispositivo por usuario y hash de fingerprint.

        Este método es crítico para detectar si un dispositivo es nuevo o conocido.
        Busca un dispositivo activo que pertenezca al usuario y tenga el mismo
        fingerprint hash.

        Args:
            user_id: ID del usuario propietario
            fingerprint_hash: Hash SHA256 del fingerprint a buscar

        Returns:
            Optional[UserDevice]: Dispositivo si existe y está activo, None en caso contrario

        Examples:
            >>> # En login, verificar si dispositivo es conocido
            >>> fingerprint = DeviceFingerprint.create(user_agent, ip)
            >>> existing = await repo.find_by_user_and_fingerprint(
            ...     user_id,
            ...     fingerprint.fingerprint_hash
            ... )
            >>> if existing:
            ...     # ✅ Dispositivo conocido
            ...     existing.update_last_used()
            ...     await repo.save(existing)
            ... else:
            ...     # ❌ Dispositivo nuevo → Crear + Email
            ...     new_device = UserDevice.create(user_id, fingerprint)
            ...     await repo.save(new_device)
        """
        pass

    @abstractmethod
    async def find_active_by_user(self, user_id: UserId) -> list[UserDevice]:
        """
        Lista todos los dispositivos activos de un usuario.

        Retorna solo dispositivos con is_active=True, ordenados por
        last_used_at descendente (más reciente primero).

        Args:
            user_id: ID del usuario

        Returns:
            List[UserDevice]: Lista de dispositivos activos (puede estar vacía)

        Examples:
            >>> # Endpoint: GET /users/me/devices
            >>> devices = await repo.find_active_by_user(user_id)
            >>> for device in devices:
            ...     print(f"{device.device_name} - Usado: {device.last_used_at}")
            Chrome on macOS - Usado: 2026-01-09 10:30:00
            Safari on iOS - Usado: 2026-01-08 14:20:00
        """
        pass

    @abstractmethod
    async def revoke(self, device_id: UserDeviceId) -> None:
        """
        Revoca un dispositivo (marca como inactivo).

        Este método es un shortcut para:
        1. Buscar dispositivo por ID
        2. Llamar a device.revoke()
        3. Guardar dispositivo

        Opcionalmente puede implementarse directamente con UPDATE en BD
        por eficiencia.

        Args:
            device_id: ID del dispositivo a revocar

        Raises:
            DeviceNotFoundError: Si el dispositivo no existe
            DeviceAlreadyRevokedError: Si ya estaba revocado

        Examples:
            >>> # Endpoint: DELETE /users/me/devices/{device_id}
            >>> device_id = UserDeviceId.from_string(request_device_id)
            >>> await repo.revoke(device_id)
        """
        pass
