"""
Los dos correos de un cambio de correo pendiente (#749): el enlace al nuevo y el aviso al
de antes. Los usan Seguridad y el panel de administración (BE #753, punto 4).
"""

import logging

from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.domain.entities.user import User

logger = logging.getLogger(__name__)


async def avisa_del_cambio_de_correo(
    email_service: IEmailService, user: User, new_email: str, token: str
) -> None:
    """
    El enlace al correo nuevo y el aviso al de antes. Un fallo no tumba el cambio, ni
    al mandarlos ni al montarlos: el cambio ya está guardado (CodeRabbit en BE #760).
    """
    try:
        envios = [
            (
                "confirmation",
                email_service.send_email_change_confirmation,
                {"to_email": new_email, "user_name": user.first_name, "token": token},
            )
        ]
        # Nunca a un correo sin confirmar (como el aviso de nuevo inicio)
        if user.email_verified:
            envios.append(
                (
                    "notice",
                    email_service.send_email_change_requested_notice,
                    {
                        "to_email": str(user.email.value),
                        "user_name": user.first_name,
                        "new_email": new_email,
                    },
                )
            )
    except Exception as error:
        logger.error("Email change mails could not be built: %s", type(error).__name__)
        return
    for nombre, envia, datos in envios:
        try:
            if not await envia(**datos):
                logger.warning("Email change %s mail not sent for a user", nombre)
        except Exception as error:
            logger.error("Email change %s mail failed: %s", nombre, type(error).__name__)
