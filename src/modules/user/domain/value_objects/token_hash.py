"""
TokenHash Value Object.

Value Object que encapsula el hash de un refresh token para almacenamiento seguro.
"""
import hashlib


class TokenHash:
    """
    Value Object para el hash de un Refresh Token.

    Almacena tokens hasheados (no en texto plano) para seguridad.
    Similar a cómo Password hashea contraseñas con bcrypt.
    """

    def __init__(self, hashed_value: str):
        """
        Inicializa un TokenHash con un valor ya hasheado.

        Args:
            hashed_value: Hash SHA256 del token en hexadecimal

        Raises:
            ValueError: Si el hash no es válido
        """
        if not isinstance(hashed_value, str):
            raise ValueError(f"Hash debe ser string. Recibido: {type(hashed_value).__name__}")

        if len(hashed_value) != 64:  # SHA256 produce 64 caracteres hex
            raise ValueError(f"Hash inválido. Debe ser SHA256 (64 chars). Recibido: {len(hashed_value)} chars")

        # Verificar que sea hexadecimal válido
        try:
            int(hashed_value, 16)
        except ValueError as e:
            raise ValueError(f"Hash debe ser hexadecimal válido: {e}") from e

        self._value = hashed_value

    @property
    def value(self) -> str:
        """Retorna el hash."""
        return self._value

    @classmethod
    def from_token(cls, token: str) -> "TokenHash":
        """
        Crea un TokenHash hasheando un token en texto plano.

        Args:
            token: Token JWT en texto plano

        Returns:
            TokenHash con el hash SHA256 del token
        """
        if not token or not isinstance(token, str):
            raise ValueError("Token debe ser un string no vacío")

        # Hashear con SHA256 (rápido, suficiente para tokens JWT)
        # No necesitamos bcrypt porque los tokens JWT ya son aleatorios y largos
        hash_obj = hashlib.sha256(token.encode('utf-8'))
        hashed = hash_obj.hexdigest()

        return cls(hashed)

    def verify(self, token: str) -> bool:
        """
        Verifica si un token coincide con este hash.

        Args:
            token: Token JWT en texto plano a verificar

        Returns:
            True si el token coincide con el hash
        """
        try:
            token_hash = TokenHash.from_token(token)
            return self._value == token_hash._value
        except ValueError:
            return False

    def __eq__(self, other: object) -> bool:
        """Compara dos TokenHashes por valor."""
        if not isinstance(other, TokenHash):
            return False
        return self._value == other._value

    def __hash__(self) -> int:
        """Hash del TokenHash para usar en sets/dicts."""
        return hash(self._value)

    def __str__(self) -> str:
        """Representación string del TokenHash (truncado por seguridad)."""
        return f"{self._value[:8]}...{self._value[-8:]}"

    def __repr__(self) -> str:
        """Representación debug del TokenHash (truncado)."""
        return f"TokenHash('{self._value[:8]}...')"
