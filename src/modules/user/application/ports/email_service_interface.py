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

    @abstractmethod
    async def send_password_reset_email(
        self,
        to_email: str,
        reset_link: str,
        user_name: str
    ) -> bool:
        """
        Envía un email con enlace para resetear contraseña.

        Args:
            to_email: Email del destinatario
            reset_link: Enlace completo para resetear contraseña (incluye token)
            user_name: Nombre del usuario para personalizar

        Returns:
            True si se envió correctamente, False en caso contrario

        Security:
            - reset_link incluye token de 256 bits válido por 24 horas
            - Email enviado solo si el usuario existe (previene enumeración)
            - Plantilla bilingüe (ES/EN)
        """
        pass

    @abstractmethod
    async def send_password_changed_notification(
        self,
        to_email: str,
        user_name: str
    ) -> bool:
        """
        Envía un email notificando que la contraseña fue cambiada exitosamente.

        Args:
            to_email: Email del destinatario
            user_name: Nombre del usuario para personalizar

        Returns:
            True si se envió correctamente, False en caso contrario

        Security:
            - Notifica al usuario de cambios de seguridad importantes
            - Permite detectar cambios de contraseña no autorizados
            - Plantilla bilingüe (ES/EN)
        """
        pass
