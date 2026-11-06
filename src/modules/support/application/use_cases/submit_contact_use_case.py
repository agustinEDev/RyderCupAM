"""
Submit Contact Use Case - Application Layer

El formulario de contacto, por correo al buzón de la app (6 nov 2026). Antes abría
una issue en un repositorio público de GitHub, con el nombre y el correo a la vista.
"""

import logging
import re
import unicodedata

from src.modules.support.application.dto.contact_dto import (
    ContactRequestDTO,
    ContactResponseDTO,
)
from src.modules.support.application.ports.contact_mailer import IContactMailer
from src.modules.support.application.ports.cupo_de_contacto_port import ICupoDeContacto
from src.modules.support.domain.value_objects.contact_category import ContactCategory

logger = logging.getLogger(__name__)

# El nombre de cada categoría en el asunto y el cuerpo
NOMBRE_DE_LA_CATEGORIA = {
    ContactCategory.BUG: "Error",
    ContactCategory.FEATURE: "Sugerencia",
    ContactCategory.QUESTION: "Pregunta",
    ContactCategory.OTHER: "Otro",
}
# Saltos de línea y demás caracteres de control: fuera de una línea (asunto, nombre)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
# En el cuerpo se conservan los saltos de línea y los tabuladores
_CONTROL_EN_EL_CUERPO = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ContactQuotaExceededError(Exception):
    """El tope diario de mensajes de contacto está lleno."""


class ContactDeliveryError(Exception):
    """El proveedor de correo no aceptó el mensaje."""


def _en_una_linea(texto: str, si_queda_vacio: str) -> str:
    """Sin saltos, caracteres de control ni invisibles (Cc, Cf: los que dan la vuelta
    al texto o no se ven), y sin espacios dobles. Si no queda nada, `si_queda_vacio`."""
    sin_control = _CONTROL.sub(" ", texto)
    visible = "".join(c for c in sin_control if unicodedata.category(c) not in ("Cc", "Cf"))
    return " ".join(visible.split()) or si_queda_vacio


class SubmitContactUseCase:
    """Manda un mensaje del formulario de contacto al buzón de la app."""

    def __init__(self, mailer: IContactMailer, cupo: ICupoDeContacto):
        """El caso de uso, con el envío del correo y el tope diario."""
        self._mailer = mailer
        self._cupo = cupo

    async def execute(self, request: ContactRequestDTO) -> ContactResponseDTO:
        """
        Manda el mensaje por correo, si cabe en el tope de hoy.

        Raises:
            ContactQuotaExceededError: si el tope diario está lleno (no se envía)
            ContactDeliveryError: si el proveedor no lo acepta (el hueco se devuelve)
        """
        if not self._cupo.reserva():
            logger.warning("Contact form daily quota reached")
            raise ContactQuotaExceededError()

        categoria = NOMBRE_DE_LA_CATEGORIA[request.category]
        nombre = _en_una_linea(request.name, "(sin nombre)")
        texto = (
            f"Nombre: {nombre}\n"
            f"Correo: {request.email}\n"
            # «Responder» va a esta dirección, y nadie la ha comprobado
            "(sin verificar: lo escribió quien envía el formulario)\n"
            f"Categoría: {categoria}\n\n"
            f"{_CONTROL_EN_EL_CUERPO.sub('', request.message)}\n"
        )
        try:
            enviado = await self._mailer.send(
                subject=f"[Contacto · {categoria}] {_en_una_linea(request.subject, '(sin asunto)')}",
                text=texto,
                reply_to=str(request.email),
            )
        except Exception as error:
            # Un fallo inesperado tampoco gasta el hueco: veinte así cerrarían el día
            logger.error("Contact form email failed: %s", type(error).__name__)
            enviado = False
        if not enviado:
            self._cupo.devuelve()
            # Sin datos de quien escribe: el log no es sitio para su correo
            logger.error("Contact form email could not be sent")
            raise ContactDeliveryError()

        return ContactResponseDTO(
            message="Your message has been received. We will get back to you soon."
        )
