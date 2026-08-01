"""
Social Email Service Interface - Application Layer Port

Define el contrato para envio de emails relacionados con el modulo Social
(amistades). Vive en el Social module (Interface Segregation Principle).
"""

from abc import ABC, abstractmethod


class ISocialEmailService(ABC):
    """
    Puerto para envio de emails relacionados con amistades.

    Separado de IEmailService (User module) e IInvitationEmailService
    (Competition module) para respetar ISP. La implementacion concreta
    (EmailService) puede implementar las tres interfaces.
    """

    @abstractmethod
    async def send_friend_request_email(
        self,
        to_email: str,
        addressee_name: str,
        requester_name: str,
    ) -> bool:
        """
        Envia un email notificando una nueva solicitud de amistad.

        Args:
            to_email: Email del destinatario de la solicitud
            addressee_name: Nombre del destinatario de la solicitud
            requester_name: Nombre de quien envia la solicitud

        Returns:
            True si se envio correctamente, False en caso contrario
        """
        pass
