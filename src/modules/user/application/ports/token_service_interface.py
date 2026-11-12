"""
Token Service Interface - Application Layer Port

Define el contrato para servicios de tokens de autenticación.
"""

from datetime import timedelta
from typing import Any, Protocol


class ITokenService(Protocol):
    """
    Puerto para servicios de generación y verificación de tokens.

    Define el contrato para sistemas de autenticación basados en tokens.

    Implementaciones posibles:
    - JWTTokenService (JWT con python-jose)
    - OAuth2TokenService (OAuth2)
    - MockTokenService (testing)
    """

    def create_access_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
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

    def verify_access_token(self, token: str) -> dict[str, Any] | None:
        """
        Verifica y decodifica un token.

        Args:
            token: Token a verificar

        Returns:
            Payload del token si es válido, None si es inválido
        """
        pass

    def verify_refresh_token(self, token: str) -> dict[str, Any] | None:
        """
        Verifica y decodifica un refresh token.

        Returns:
            Payload si es válido (firma, caducidad y tipo), None si no
        """

    def refresh_token_expired(self, token: str) -> bool:
        """
        Si es un refresh token de esta API, con la firma buena, que ya ha caducado.

        Distingue el final normal de una sesión de un token inválido (FE #1042).
        """

    def create_refresh_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        """Crea un refresh token (7 días por defecto)."""

    def create_csrf_token(self, user_id: str) -> str:
        """
        Crea el token CSRF de la sesión, firmado para ese usuario (BE #724).

        Se emite junto al de acceso y al de refresco en el login, en el de
        Google y en cada refresco. Los casos de uso lo piden aquí en vez de
        importar la configuración CSRF (auditoría de arquitectura, 9 nov 2026).
        """
