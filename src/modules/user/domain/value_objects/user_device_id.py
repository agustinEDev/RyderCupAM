"""
Value Object para el identificador único de un dispositivo de usuario.

Este módulo define UserDeviceId, un Value Object que encapsula la lógica
de identificación única de dispositivos en el sistema.

Responsabilidades:
- Generar identificadores únicos (UUID v4)
- Validar formato de UUIDs
- Proporcionar representación inmutable del identificador
- Garantizar unicidad mediante UUID estándar

Características:
- Inmutable (no puede modificarse después de creación)
- Validación automática en construcción
- Soporte para generación y reconstrucción desde string
- Comparación por valor (equality)
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class UserDeviceId:
    """
    Value Object que representa el identificador único de un dispositivo.

    Este VO garantiza que cada dispositivo tenga un identificador único
    válido según el estándar UUID v4.

    Attributes:
        value (uuid.UUID): El UUID que identifica al dispositivo

    Examples:
        >>> # Generar nuevo ID
        >>> device_id = UserDeviceId.generate()

        >>> # Reconstruir desde string
        >>> device_id = UserDeviceId.from_string("550e8400-e29b-41d4-a716-446655440000")

        >>> # Obtener string
        >>> str(device_id)
        '550e8400-e29b-41d4-a716-446655440000'
    """

    value: uuid.UUID

    @staticmethod
    def generate() -> "UserDeviceId":
        """
        Genera un nuevo UserDeviceId único.

        Utiliza UUID v4 (aleatorio) para garantizar unicidad global
        sin necesidad de coordinación centralizada.

        Returns:
            UserDeviceId: Nuevo identificador único generado

        Examples:
            >>> device_id = UserDeviceId.generate()
            >>> isinstance(device_id.value, uuid.UUID)
            True
        """
        return UserDeviceId(value=uuid.uuid4())

    @staticmethod
    def from_string(id_str: str) -> "UserDeviceId":
        """
        Crea un UserDeviceId desde una representación en string.

        Útil para reconstruir el VO desde la base de datos o desde
        requests HTTP.

        Args:
            id_str: String con formato UUID válido

        Returns:
            UserDeviceId: Value Object reconstruido

        Raises:
            ValueError: Si el string no es un UUID válido

        Examples:
            >>> device_id = UserDeviceId.from_string("550e8400-e29b-41d4-a716-446655440000")
            >>> str(device_id)
            '550e8400-e29b-41d4-a716-446655440000'
        """
        try:
            uuid_value = uuid.UUID(id_str)
            return UserDeviceId(value=uuid_value)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"ID de dispositivo inválido: {id_str}") from e

    def __str__(self) -> str:
        """
        Representación en string del UserDeviceId.

        Returns:
            str: UUID en formato string (con guiones)

        Examples:
            >>> device_id = UserDeviceId.generate()
            >>> len(str(device_id))
            36
        """
        return str(self.value)

    def __repr__(self) -> str:
        """
        Representación técnica del UserDeviceId para debugging.

        Returns:
            str: Representación completa del objeto

        Examples:
            >>> device_id = UserDeviceId.generate()
            >>> repr(device_id)
            "UserDeviceId(value=UUID('...'))"
        """
        return f"UserDeviceId(value={self.value!r})"

    def __eq__(self, other: object) -> bool:
        """
        Compara dos UserDeviceId por valor.

        Dos UserDeviceId son iguales si sus UUIDs son iguales.

        Args:
            other: Otro objeto a comparar

        Returns:
            bool: True si son iguales, False en caso contrario

        Examples:
            >>> id1 = UserDeviceId.from_string("550e8400-e29b-41d4-a716-446655440000")
            >>> id2 = UserDeviceId.from_string("550e8400-e29b-41d4-a716-446655440000")
            >>> id1 == id2
            True
        """
        if not isinstance(other, UserDeviceId):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        """
        Genera hash del UserDeviceId.

        Permite usar UserDeviceId como clave de diccionario o en sets.

        Returns:
            int: Hash del UUID interno

        Examples:
            >>> device_id = UserDeviceId.generate()
            >>> isinstance(hash(device_id), int)
            True
        """
        return hash(self.value)
