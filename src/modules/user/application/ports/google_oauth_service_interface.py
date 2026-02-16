"""
Google OAuth Service Interface - Application Layer Port

Define el contrato para el servicio de autenticación con Google OAuth.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GoogleUserInfo:
    """Información del usuario obtenida de Google OAuth."""

    google_user_id: str
    email: str
    first_name: str
    last_name: str
    email_verified: bool = False
    picture_url: str | None = None


class IGoogleOAuthService(ABC):
    """
    Puerto para el servicio de Google OAuth.

    Intercambia un authorization code por información del usuario de Google.
    """

    @abstractmethod
    async def exchange_code_for_user_info(self, authorization_code: str) -> GoogleUserInfo:
        """
        Intercambia un authorization code de Google por información del usuario.

        Args:
            authorization_code: Código de autorización de Google (del frontend)

        Returns:
            GoogleUserInfo con datos del usuario de Google

        Raises:
            ValueError: Si el código es inválido o expirado
        """
        pass
