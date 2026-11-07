"""
Lo que no se probó de una cuenta SIN verificar, fuera (#749, pre-captura).

Cuando alguien demuestra que el correo de una cuenta sin verificar es suyo (entra con
un Google que lo verificó, o restablece la contraseña con el enlace de su buzón), lo
que dejó quien la creó o le cambió el correo no vale: sus dispositivos, sus sesiones y
el Google que hubiera vinculado. Dentro de la transacción del que llama.
"""

import logging

from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.services.revoca_sus_sesiones import revoca_sus_sesiones
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.oauth_provider import OAuthProvider
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


async def cierra_lo_que_no_se_probo(
    uow: UserUnitOfWorkInterface, user_id: UserId
) -> tuple[int, int, int]:
    """Revoca dispositivos y sesiones y quita su Google. Devuelve cuántos de cada."""
    dispositivos, tokens = await revoca_sus_sesiones(uow, user_id)
    google = await uow.oauth_accounts.find_by_user_id_and_provider(user_id, OAuthProvider.GOOGLE)
    if google is not None:
        await uow.oauth_accounts.delete(google)
    return dispositivos, tokens, int(google is not None)


async def avisa_de_la_toma(email_service: IEmailService, user: User, via: str) -> None:
    """
    Avisa al dueño, ya demostrado, de que se ha asegurado su cuenta (BE #753). Tras la
    transacción: si falla, la toma ya está hecha.
    """
    try:
        enviado = await email_service.send_account_secured_notice(
            to_email=str(user.email.value), user_name=user.first_name, via=via
        )
    except Exception as error:
        logger.error("Account secured notice failed: %s", type(error).__name__)
        return
    if not enviado:
        logger.error("Account secured notice was not sent")


async def avisa_de_google(email_service: IEmailService, user: User, linked: bool) -> None:
    """
    El aviso de Google vinculado o desvinculado (BE #753), tras la transacción y solo a
    un correo verificado. Si falla, la operación ya está hecha.
    """
    if not user.email_verified:
        return
    try:
        enviado = await email_service.send_google_account_notice(
            to_email=str(user.email.value), user_name=user.first_name, linked=linked
        )
    except Exception as error:
        logger.error("Google account notice failed: %s", type(error).__name__)
        return
    if not enviado:
        logger.error("Google account notice was not sent")
