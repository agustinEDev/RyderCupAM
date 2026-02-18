"""
Invitation Email Service Interface - Application Layer Port

Define el contrato para envio de emails de invitacion.
Vive en el Competition module (Interface Segregation Principle).
"""

from abc import ABC, abstractmethod
from datetime import datetime


class IInvitationEmailService(ABC):
    """
    Puerto para envio de emails de invitacion a competiciones.

    Separado de IEmailService (User module) para respetar ISP.
    La implementacion concreta (EmailService) puede implementar ambas interfaces.
    """

    @abstractmethod
    async def send_invitation_email(
        self,
        to_email: str,
        invitee_name: str | None,
        inviter_name: str,
        competition_name: str,
        personal_message: str | None,
        expires_at: datetime,
    ) -> bool:
        """
        Envia un email de invitacion a una competicion.

        Args:
            to_email: Email del invitado
            invitee_name: Nombre del invitado (None si no registrado)
            inviter_name: Nombre del que invita
            competition_name: Nombre de la competicion
            personal_message: Mensaje personal opcional
            expires_at: Fecha de expiracion de la invitacion

        Returns:
            True si se envio correctamente, False en caso contrario
        """
        pass
