"""
Contact Mailer - Infrastructure Layer

Manda los mensajes del formulario de contacto al buzón de la app, en texto plano y con
«Responder a» quien escribe (6 nov 2026). Desde el 7 nov, por la pieza común de envío
(Mailgun con Brevo de respaldo, o Mailpit en el Kind).
"""

import os

from src.config.settings import settings
from src.modules.support.application.ports.contact_mailer import IContactMailer
from src.shared.infrastructure.email.envio_de_correo import (
    CorreoSaliente,
    EnvioConRespaldo,
    crea_el_envio,
)


class ContactMailer(IContactMailer):
    """El mensaje de contacto, al buzón de CONTACT_EMAIL."""

    def __init__(self, envio: EnvioConRespaldo | None = None, to_email: str | None = None):
        """Con el envío y el buzón de la configuración, salvo los que se pasen (tests)."""
        self._envio = envio or crea_el_envio(os.environ)
        self._to_email = to_email

    async def send(self, subject: str, text: str, reply_to: str) -> bool:
        """Lo manda; False si no salió (sin clave, cupo, red...)."""
        # Una dirección con tildes no se puede poner en una cabecera: sin «Responder a»
        # (la dirección ya va en el cuerpo)
        return await self._envio.send(
            CorreoSaliente(
                to=self._to_email or settings.CONTACT_EMAIL,
                subject=subject,
                text=text,
                reply_to=reply_to if reply_to.isascii() else None,
                # Sin token: puede salir por Brevo si Mailgun no puede
                con_token=False,
            )
        )
