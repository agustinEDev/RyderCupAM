"""
Entidad de dominio UserDevice - Dispositivo de usuario.

Este módulo define la entidad UserDevice, que representa un dispositivo
registrado desde el cual un usuario ha accedido al sistema.

Responsabilidades:
- Crear nuevos dispositivos con validación completa
- Gestionar ciclo de vida del dispositivo (activo/revocado)
- Actualizar información de último uso
- Disparar eventos de dominio (NewDeviceDetected, DeviceRevoked)
- Mantener invariantes del dominio (consistencia)

Reglas de Negocio:
- Un dispositivo pertenece a UN solo usuario
- Un dispositivo tiene fingerprint único (hash)
- Un dispositivo puede estar activo o revocado (soft delete)
- Un dispositivo revocado NO puede reactivarse (crear uno nuevo)
- Cada acceso actualiza el timestamp de último uso
"""

from datetime import datetime

from sqlalchemy.orm import reconstructor

from src.modules.user.domain.events.device_revoked_event import DeviceRevokedEvent
from src.modules.user.domain.events.new_device_detected_event import (
    NewDeviceDetectedEvent,
)
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent


class UserDevice:
    """
    Entidad que representa un dispositivo desde el cual un usuario accede al sistema.

    Esta entidad es el Aggregate Root del contexto de Device Fingerprinting.
    Encapsula toda la lógica de negocio relacionada con dispositivos de usuario.

    Attributes (privados):
        _id (UserDeviceId): Identificador único del dispositivo
        _user_id (UserId): ID del usuario propietario
        _fingerprint (DeviceFingerprint): Huella digital del dispositivo
        _is_active (bool): Estado del dispositivo (True=activo, False=revocado)
        _last_used_at (datetime): Última vez que se usó el dispositivo
        _created_at (datetime): Timestamp de creación del registro
        _domain_events (List[DomainEvent]): Lista de eventos pendientes

    Properties (públicos):
        id, user_id, fingerprint, device_name, fingerprint_hash,
        ip_address, user_agent, is_active, last_used_at, created_at

    Examples:
        >>> # Crear nuevo dispositivo
        >>> fingerprint = DeviceFingerprint.create("Mozilla/5.0...", "192.168.1.100")
        >>> device = UserDevice.create(user_id, fingerprint)
        >>> device.device_name
        'Chrome on macOS'

        >>> # Revocar dispositivo
        >>> device.revoke()
        >>> device.is_active
        False
    """

    def __init__(
        self,
        id: UserDeviceId,
        user_id: UserId,
        device_name: str,
        user_agent: str,
        ip_address: str,
        fingerprint_hash: str,
        is_active: bool,
        last_used_at: datetime,
        created_at: datetime,
    ) -> None:
        """
        Constructor privado de UserDevice.

        IMPORTANTE: NO usar directamente. Usar métodos factory:
        - UserDevice.create() para dispositivos nuevos
        - UserDevice.reconstitute() para reconstruir desde BD

        Args:
            id: Identificador único del dispositivo
            user_id: ID del usuario propietario
            device_name: Nombre legible del dispositivo
            user_agent: User-Agent HTTP header
            ip_address: IP normalizada
            fingerprint_hash: Hash SHA256 del fingerprint
            is_active: Estado del dispositivo
            last_used_at: Último timestamp de uso
            created_at: Timestamp de creación
        """
        self._id = id
        self._user_id = user_id
        self._device_name = device_name
        self._user_agent = user_agent
        self._ip_address = ip_address
        self._fingerprint_hash = fingerprint_hash
        self._is_active = is_active
        self._last_used_at = last_used_at
        self._created_at = created_at
        self._domain_events: list[DomainEvent] = []

    @reconstructor
    def _init_on_load(self):
        """
        Inicializa atributos cuando SQLAlchemy reconstruye la entidad desde BD.

        SQLAlchemy no llama a __init__() al cargar desde la BD, por lo que
        necesitamos este método para inicializar _domain_events.

        Este es un método especial de SQLAlchemy que se ejecuta automáticamente
        después de cargar la entidad.

        Note:
            - Solo se ejecuta cuando SQLAlchemy carga desde BD
            - NO se ejecuta cuando se crea con __init__() directamente
            - Necesario para evitar AttributeError en métodos que usan _domain_events
        """
        if not hasattr(self, "_domain_events"):
            self._domain_events = []

    @staticmethod
    def create(user_id: UserId, fingerprint: DeviceFingerprint) -> "UserDevice":
        """
        Factory method para crear un nuevo dispositivo.

        Este es el método principal para crear dispositivos nuevos cuando
        se detecta un login desde un dispositivo desconocido.

        Automáticamente:
        1. Genera un ID único
        2. Marca el dispositivo como activo
        3. Establece timestamps (created_at, last_used_at)
        4. Dispara el evento NewDeviceDetectedEvent

        Args:
            user_id: ID del usuario propietario del dispositivo
            fingerprint: Huella digital del dispositivo (con hash, nombre, etc.)

        Returns:
            UserDevice: Nueva entidad de dispositivo

        Raises:
            ValueError: Si user_id o fingerprint son inválidos

        Examples:
            >>> user_id = UserId.generate()
            >>> fingerprint = DeviceFingerprint.create("Mozilla/5.0...", "192.168.1.100")
            >>> device = UserDevice.create(user_id, fingerprint)
            >>> device.is_active
            True
            >>> len(device.domain_events())
            1  # NewDeviceDetectedEvent
        """
        # Validaciones
        if not isinstance(user_id, UserId):
            raise ValueError("user_id debe ser una instancia de UserId")
        if not isinstance(fingerprint, DeviceFingerprint):
            raise ValueError("fingerprint debe ser una instancia de DeviceFingerprint")

        # Crear entidad
        now = datetime.now()
        device = UserDevice(
            id=UserDeviceId.generate(),
            user_id=user_id,
            device_name=fingerprint.device_name,
            user_agent=fingerprint.user_agent,
            ip_address=fingerprint.ip_address,
            fingerprint_hash=fingerprint.fingerprint_hash,
            is_active=True,
            last_used_at=now,
            created_at=now,
        )

        # Disparar evento de dominio
        event = NewDeviceDetectedEvent(
            user_id=user_id,
            device_name=fingerprint.device_name,
            ip_address=fingerprint.ip_address,
            user_agent=fingerprint.user_agent,
        )
        device._add_domain_event(event)

        return device

    @staticmethod
    def reconstitute(
        id: UserDeviceId,
        user_id: UserId,
        device_name: str,
        user_agent: str,
        ip_address: str,
        fingerprint_hash: str,
        is_active: bool,
        last_used_at: datetime,
        created_at: datetime,
    ) -> "UserDevice":
        """
        Factory method para reconstruir un dispositivo desde la base de datos.

        Este método NO dispara eventos (la entidad ya existía).
        Se usa cuando el repository lee dispositivos de la BD.

        Args:
            id: ID del dispositivo (ya existente)
            user_id: ID del usuario propietario
            device_name: Nombre legible del dispositivo
            user_agent: User-Agent HTTP header
            ip_address: IP normalizada
            fingerprint_hash: Hash SHA256
            is_active: Estado del dispositivo
            last_used_at: Último timestamp de uso
            created_at: Timestamp de creación original

        Returns:
            UserDevice: Entidad reconstruida desde BD
        """
        device = UserDevice(
            id=id,
            user_id=user_id,
            device_name=device_name,
            user_agent=user_agent,
            ip_address=ip_address,
            fingerprint_hash=fingerprint_hash,
            is_active=is_active,
            last_used_at=last_used_at,
            created_at=created_at,
        )
        # NO disparar eventos (ya existía)
        return device

    def revoke(self) -> None:
        """
        Revoca el dispositivo (soft delete).

        Marca el dispositivo como inactivo. El usuario no podrá usarlo
        más para autenticarse, pero el registro se mantiene en BD para auditoría.

        Un dispositivo revocado NO puede reactivarse. Si el usuario vuelve
        a usar ese dispositivo, se creará un nuevo registro.

        Dispara el evento DeviceRevokedEvent.

        Raises:
            ValueError: Si el dispositivo ya estaba revocado

        Examples:
            >>> device = UserDevice.create(user_id, fingerprint)
            >>> device.is_active
            True
            >>> device.revoke()
            >>> device.is_active
            False
            >>> len(device.domain_events())
            2  # NewDeviceDetected + DeviceRevoked
        """
        if not self._is_active:
            raise RuntimeError("Device already revoked")

        self._is_active = False

        # Disparar evento de dominio
        event = DeviceRevokedEvent(
            user_id=self._user_id,
            device_id=self._id,
            device_name=self._device_name,
            revoked_by_user=True,  # Manual por usuario (API endpoint)
        )
        self._add_domain_event(event)

    def revoke_automatically(self) -> None:
        """
        Revoca el dispositivo automáticamente (por política del sistema).

        Similar a revoke(), pero marca revoked_by_user=False en el evento
        para distinguir revocaciones automáticas (cleanup, políticas) de
        revocaciones manuales del usuario.

        Raises:
            ValueError: Si el dispositivo ya estaba revocado

        Examples:
            >>> # Sistema ejecuta cleanup de dispositivos viejos
            >>> device.revoke_automatically()
            >>> device.is_active
            False
        """
        if not self._is_active:
            raise RuntimeError("Device already revoked")

        self._is_active = False

        # Disparar evento con revoked_by_user=False
        event = DeviceRevokedEvent(
            user_id=self._user_id,
            device_id=self._id,
            device_name=self._device_name,
            revoked_by_user=False,  # Automático por sistema
        )
        self._add_domain_event(event)

    def update_last_used(self) -> None:
        """
        Actualiza el timestamp de último uso al momento actual.

        Se llama cada vez que el usuario hace login desde este dispositivo.
        Permite trackear dispositivos inactivos para futuras políticas de cleanup.

        Examples:
            >>> device = UserDevice.create(user_id, fingerprint)
            >>> original_time = device.last_used_at
            >>> # ... pasa tiempo ...
            >>> device.update_last_used()
            >>> device.last_used_at > original_time
            True
        """
        self._last_used_at = datetime.now()

    def update_ip_address(self, ip_address: str) -> None:
        """
        Actualiza la dirección IP del dispositivo (audit trail).

        Se llama cuando el dispositivo es identificado via cookie y la IP
        ha cambiado desde la última vez. Permite mantener un registro de
        la última IP conocida para auditoría de seguridad.

        Args:
            ip_address: Nueva dirección IP del dispositivo

        Examples:
            >>> device = UserDevice.create(user_id, fingerprint)
            >>> device.ip_address
            '192.168.1.100'
            >>> device.update_ip_address('192.168.1.200')
            >>> device.ip_address
            '192.168.1.200'

        Note:
            - No dispara eventos de dominio (es solo audit)
            - La IP se almacena tal cual se recibe (no se normaliza)
        """
        self._ip_address = ip_address

    def matches_fingerprint(self, fingerprint: DeviceFingerprint) -> bool:
        """
        Verifica si el fingerprint dado coincide con el de este dispositivo.

        Compara los hashes SHA256. Si coinciden, es el mismo dispositivo.

        Args:
            fingerprint: Fingerprint a comparar

        Returns:
            bool: True si coincide (mismo dispositivo), False en caso contrario

        Examples:
            >>> fp1 = DeviceFingerprint.create("Mozilla/5.0...", "192.168.1.100")
            >>> device = UserDevice.create(user_id, fp1)
            >>> fp2 = DeviceFingerprint.create("Mozilla/5.0...", "192.168.1.100")
            >>> device.matches_fingerprint(fp2)
            True
        """
        return self._fingerprint_hash == fingerprint.fingerprint_hash

    # ==========================================================================
    # DOMAIN EVENTS MANAGEMENT
    # ==========================================================================

    def _add_domain_event(self, event: DomainEvent) -> None:
        """
        Registra un evento de dominio pendiente.

        Los eventos se procesan después de persistir la entidad.

        Args:
            event: Evento de dominio a registrar
        """
        self._domain_events.append(event)

    def domain_events(self) -> list[DomainEvent]:
        """
        Obtiene la lista de eventos de dominio pendientes.

        Returns:
            List[DomainEvent]: Lista de eventos (copia)
        """
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        """
        Limpia la lista de eventos de dominio.

        Se llama después de procesar los eventos.
        """
        self._domain_events.clear()

    # ==========================================================================
    # PROPERTIES (Encapsulación - solo lectura)
    # ==========================================================================

    @property
    def id(self) -> UserDeviceId:
        """ID único del dispositivo."""
        return self._id

    @property
    def user_id(self) -> UserId:
        """ID del usuario propietario."""
        return self._user_id

    @property
    def device_name(self) -> str:
        """Nombre legible del dispositivo (ej: 'Chrome on macOS')."""
        return self._device_name

    @property
    def fingerprint_hash(self) -> str:
        """Hash SHA256 del fingerprint."""
        return self._fingerprint_hash

    @property
    def ip_address(self) -> str:
        """Dirección IP normalizada del dispositivo."""
        return self._ip_address

    @property
    def user_agent(self) -> str:
        """User-Agent HTTP header completo."""
        return self._user_agent

    @property
    def is_active(self) -> bool:
        """Estado del dispositivo (True=activo, False=revocado)."""
        return self._is_active

    @property
    def last_used_at(self) -> datetime:
        """Timestamp del último uso del dispositivo."""
        return self._last_used_at

    @property
    def created_at(self) -> datetime:
        """Timestamp de creación del registro."""
        return self._created_at

    # ==========================================================================
    # MAGIC METHODS
    # ==========================================================================

    def __eq__(self, other: object) -> bool:
        """
        Compara dos UserDevice por identidad (ID).

        Dos dispositivos son iguales si tienen el mismo ID.

        Args:
            other: Otro objeto a comparar

        Returns:
            bool: True si tienen el mismo ID
        """
        if not isinstance(other, UserDevice):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        """
        Genera hash del UserDevice basado en su ID.

        Returns:
            int: Hash del ID
        """
        return hash(self._id)

    def __repr__(self) -> str:
        """
        Representación técnica para debugging.

        Returns:
            str: Representación legible
        """
        return (
            f"UserDevice("
            f"id={self._id}, "
            f"user_id={self._user_id}, "
            f"device='{self.device_name}', "
            f"active={self._is_active})"
        )
