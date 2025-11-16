"""
Token Service Interface - Application Layer Port

Define el contrato para servicios de tokens de autenticación.
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import timedelta


class ITokenService(ABC):
    """
    Puerto para servicios de generación y verificación de tokens.

    Define el contrato para sistemas de autenticación basados en tokens.

    Implementaciones posibles:
    - JWTTokenService (JWT con python-jose)
    - OAuth2TokenService (OAuth2)
    - MockTokenService (testing)
    """

    @abstractmethod
    def create_access_token(
        self,
        data: dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Crea un token de acceso.

        Args:
            data: Datos a incluir en el token (ej: {"sub": user_id})
            expires_delta: Tiempo de expiración personalizado (opcional)

        Returns:
            Token codificado como string
        """
        pass

    @abstractmethod
    def verify_access_token(self, token: str) -> Optional[dict]:
        """
        Verifica y decodifica un token.

        Args:
            token: Token a verificar

        Returns:
            Payload del token si es válido, None si es inválido
        """
        pass
