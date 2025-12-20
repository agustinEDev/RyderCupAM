"""
RefreshToken ID Value Object.

Value Object que encapsula el identificador único de un refresh token.
"""
import uuid


class RefreshTokenId:
    """
    Value Object para el ID de un Refresh Token.

    Encapsula la lógica de validación del identificador único de un token.
    """

    def __init__(self, value: str | uuid.UUID):
        """
        Inicializa un RefreshTokenId.

        Args:
            value: UUID como string o objeto UUID

        Raises:
            ValueError: Si el ID no es un UUID válido
        """
        if isinstance(value, uuid.UUID):
            self._value = value
        elif isinstance(value, str):
            try:
                self._value = uuid.UUID(value)
            except ValueError as e:
                raise ValueError(f"ID inválido: {value}. Debe ser un UUID válido.") from e
        else:
            raise ValueError(f"ID debe ser string o UUID. Recibido: {type(value).__name__}")

    @property
    def value(self) -> uuid.UUID:
        """Retorna el UUID."""
        return self._value

    @classmethod
    def generate(cls) -> "RefreshTokenId":
        """Genera un nuevo RefreshTokenId único."""
        return cls(uuid.uuid4())

    def __eq__(self, other: object) -> bool:
        """Compara dos RefreshTokenIds por valor."""
        if not isinstance(other, RefreshTokenId):
            return False
        return self._value == other._value

    def __hash__(self) -> int:
        """Hash del RefreshTokenId para usar en sets/dicts."""
        return hash(self._value)

    def __str__(self) -> str:
        """Representación string del RefreshTokenId."""
        return str(self._value)

    def __repr__(self) -> str:
        """Representación debug del RefreshTokenId."""
        return f"RefreshTokenId('{self._value}')"
