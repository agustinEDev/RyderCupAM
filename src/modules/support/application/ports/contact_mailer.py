"""
Contact Mailer - Application Layer Port

El envío por correo de un mensaje del formulario de contacto (6 nov 2026). Antes se
abría una issue en un repositorio público de GitHub, con el nombre y el correo.
"""

from abc import ABC, abstractmethod


class IContactMailer(ABC):
    """Manda un mensaje de contacto al buzón de la app."""

    @abstractmethod
    async def send(self, subject: str, text: str, reply_to: str) -> bool:
        """
        Manda el mensaje, en texto plano.

        Args:
            subject: El asunto, en una línea
            text: El cuerpo, en texto plano
            reply_to: El correo de quien escribe, para «Responder»

        Returns:
            True si el proveedor lo aceptó
        """
