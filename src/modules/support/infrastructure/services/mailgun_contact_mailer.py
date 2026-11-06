"""
Mailgun Contact Mailer - Infrastructure Layer

Manda los mensajes del formulario de contacto al buzón de la app por Mailgun (UE),
en texto plano y con «Responder a» quien escribe (6 nov 2026).
"""

import logging

import httpx

from src.config.settings import settings
from src.modules.support.application.ports.contact_mailer import IContactMailer

logger = logging.getLogger(__name__)

HTTP_OK = 200


class MailgunContactMailer(IContactMailer):
    """El mensaje de contacto, por la API de Mailgun."""

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        domain: str | None = None,
        from_email: str | None = None,
        to_email: str | None = None,
    ):
        """Con los ajustes de la app, salvo los que se pasen (tests)."""
        self._api_key = settings.MAILGUN_API_KEY if api_key is None else api_key
        self._api_url = api_url or settings.MAILGUN_API_URL
        self._domain = domain or settings.MAILGUN_DOMAIN
        self._from_email = from_email or settings.MAILGUN_FROM_EMAIL
        self._to_email = to_email or settings.CONTACT_EMAIL

    async def send(self, subject: str, text: str, reply_to: str) -> bool:
        """Lo manda; False si no hay clave, si Mailgun no lo acepta o si no hay red."""
        if not self._api_key:
            logger.error("MAILGUN_API_KEY is not set: contact message not sent")
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as cliente:
                respuesta = await cliente.post(
                    f"{self._api_url}/{self._domain}/messages",
                    auth=("api", self._api_key),
                    data={
                        "from": self._from_email,
                        "to": self._to_email,
                        "subject": subject,
                        "text": text,
                        "h:Reply-To": reply_to,
                    },
                )
        except httpx.HTTPError as error:
            logger.error("Contact message: Mailgun unreachable (%s)", type(error).__name__)
            return False
        if respuesta.status_code != HTTP_OK:
            # Sin el cuerpo de la respuesta: podría repetir datos del mensaje
            logger.error("Contact message refused by Mailgun: %s", respuesta.status_code)
            return False
        return True
