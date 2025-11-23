"""
Email Service Interface - Application Layer Port

Define el contrato para servicios de envío de emails.
La capa de aplicación depende de esta abstracción, no de implementaciones concretas.
"""

from abc import ABC, abstractmethod


class IEmailService(ABC):
    """
    Puerto para servicios de envío de email.

    Esta interfaz vive en la capa de APPLICATION, pero es implementada
    por la capa de INFRASTRUCTURE.

    Implementaciones posibles:
    - MailgunEmailService (producción)
    - SendGridEmailService (alternativa)
    - MockEmailService (testing)
    """

    @abstractmethod
    def send_verification_email(
        self,
        to_email: str,
        user_name: str,
        verification_token: str
    ) -> bool:
        """
        Envía un email de verificación al usuario.

        Args:
            to_email: Email del destinatario
            user_name: Nombre del usuario para personalizar
            verification_token: Token único de verificación

        Returns:
            True si se envió correctamente, False en caso contrario
        """
        pass
