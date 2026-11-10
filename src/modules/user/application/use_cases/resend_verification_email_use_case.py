"""
Resend Verification Email Use Case - Application Layer

Caso de uso para reenviar el email de verificación a un usuario.
"""

import logging
import secrets

from src.modules.user.application.ports.correo_en_segundo_plano_port import (
    ICorreoEnSegundoPlano,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.user_finder import UserFinder
from src.modules.user.domain.value_objects.email import Email

logger = logging.getLogger(__name__)


class ResendVerificationError(ValueError):
    """Exception raised when resend verification fails due to security constraints."""

    pass


# Generic error message to prevent user enumeration
GENERIC_ERROR_MESSAGE = (
    "Si el email existe y no está verificado, se enviará un email de verificación"
)


class ResendVerificationEmailUseCase:
    """
    Caso de uso para reenviar el email de verificación a un usuario.

    Genera un enlace nuevo (vale 48 h; se guarda su hash y el anterior deja de valer) y
    lo envía. Con el envío en segundo plano (fase 3, B-2) la respuesta no espera al
    proveedor de correo: tarda lo mismo exista o no la cuenta.
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        email_service: IEmailService | None = None,
        *,
        correo_en_segundo_plano: ICorreoEnSegundoPlano | None = None,
    ):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)
        self._email_service = email_service
        # Sin él (tests de antes), el correo se espera aquí y su fallo se dice
        self._correo_en_segundo_plano = correo_en_segundo_plano

    async def execute(self, email: str) -> bool:
        """
        Ejecuta el caso de uso de reenvío de email de verificación.

        Args:
            email: Email del usuario al que reenviar la verificación

        Returns:
            bool: True si el correo salió (o quedó lanzado en segundo plano)

        Raises:
            ResendVerificationError: Si el email no existe, ya está verificado, no hay
                servicio de correo o (sin segundo plano) el envío falla
        """
        if not email or email.strip() == "":
            raise ResendVerificationError("El email es requerido")
        verification_token = secrets.token_urlsafe(32)
        # Una transacción: la cuenta, sin verificar, y el hash del enlace nuevo
        async with self._uow:
            email_vo = Email(email)
            user = await self._user_finder.by_email(email_vo)
            if not user or user.is_email_verified():
                raise ResendVerificationError(GENERIC_ERROR_MESSAGE)
            if not self._email_service:
                logger.error("Email service no está disponible")
                raise ResendVerificationError("Servicio de email no disponible")
            user.set_verification_token(verification_token)
            await self._uow.users.save(user)
            user_id = user.id.value
            user_name = user.get_full_name()
            # El context manager (__aexit__) hace commit automático

        email_service = self._email_service

        async def envia() -> bool:
            enviado = await email_service.send_verification_email(
                to_email=email, user_name=user_name, verification_token=verification_token
            )
            if not enviado:
                logger.error("No se pudo enviar el email de verificación al usuario %s", user_id)
            return enviado

        if self._correo_en_segundo_plano is not None:
            self._correo_en_segundo_plano.lanza("reenvio-de-verificacion", envia)
            return True

        if not await envia():
            raise ResendVerificationError("Error al enviar el email de verificación")
        logger.info("Email de verificación reenviado correctamente al usuario %s", user_id)
        return True
