"""
Resend Verification Email Use Case - Application Layer

El reenvío del enlace de verificación, de dos formas (fase 3, revisión; decidido por
Agustín):
- Con sesión (el aviso de la app), por el correo de la propia cuenta: la ruta comprueba
  que es el de la sesión.
- Sin sesión, presentando el enlace CADUCADO de la cuenta: prueba de tener el buzón.
  Nadie provoca el correo con una dirección ajena ni anula enlaces.

En las dos, el correo sale y DESPUÉS se guarda el enlace nuevo (`EnvioDeLaVerificacion`):
si el envío falla, el de antes sigue valiendo. Con el reenvío en segundo plano la
respuesta no espera al proveedor.
"""

import logging
import secrets
from datetime import datetime

from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.reenvio_de_verificacion_port import (
    IReenvioDeVerificacion,
    ReenvioDeVerificacion,
)
from src.modules.user.application.services.envio_de_la_verificacion import (
    EnvioDeLaVerificacion,
)
from src.modules.user.domain.entities.user import User
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


class _Reenvio:
    """Lo común: un token nuevo para la cuenta y su envío (en segundo plano o aquí)."""

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        email_service: IEmailService | None,
        reenvio: IReenvioDeVerificacion | None,
    ):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)
        self._email_service = email_service
        # Sin él (tests de antes), el envío y el guardado se esperan aquí
        self._reenvio = reenvio

    async def _envia(self, user: User, to_email: str) -> bool:
        """Envía un enlace nuevo a la cuenta; se guarda después, si sale."""
        if not self._email_service:
            logger.error("Email service no está disponible")
            raise ResendVerificationError("Servicio de email no disponible")
        datos = ReenvioDeVerificacion(
            user_id=user.id,
            to_email=to_email,
            user_name=user.get_full_name(),
            token=secrets.token_urlsafe(32),
        )
        if self._reenvio is not None:
            self._reenvio.lanza(datos)
            return True
        return await EnvioDeLaVerificacion(self._uow, self._email_service).envia_y_guarda(datos)


class ResendVerificationEmailUseCase(_Reenvio):
    """El reenvío por correo: el de la cuenta con sesión (lo comprueba la ruta)."""

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        email_service: IEmailService | None = None,
        *,
        reenvio: IReenvioDeVerificacion | None = None,
    ):
        super().__init__(uow, email_service, reenvio)

    async def execute(self, email: str) -> bool:
        """
        Args:
            email: El correo de la cuenta (el de la sesión)

        Returns:
            bool: True si el correo salió (o quedó lanzado en segundo plano)

        Raises:
            ResendVerificationError: Si el email no existe, ya está verificado, no hay
                servicio de correo o (sin segundo plano) el envío falla
        """
        if not email or email.strip() == "":
            raise ResendVerificationError("El email es requerido")
        async with self._uow:
            user = await self._user_finder.by_email(Email(email))
        if not user or user.is_email_verified():
            raise ResendVerificationError(GENERIC_ERROR_MESSAGE)
        if not await self._envia(user, email):
            raise ResendVerificationError("Error al enviar el email de verificación")
        logger.info("Email de verificación reenviado al usuario %s", user.id.value)
        return True


class ResendVerificationFromLinkUseCase(_Reenvio):
    """El reenvío sin sesión: con el enlace caducado de la cuenta como prueba."""

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        email_service: IEmailService | None = None,
        *,
        reenvio: IReenvioDeVerificacion | None = None,
    ):
        super().__init__(uow, email_service, reenvio)

    async def execute(self, token: str) -> bool:
        """
        Envía un enlace nuevo si `token` es el enlace de la cuenta, sin verificar, y ya
        caducado. Si no (otro token, o aún vigente: que lo use), no hace nada.

        Returns:
            True si se envió (o se lanzó); False si no tocaba. La ruta responde igual
        """
        if not token:
            return False
        async with self._uow:
            user = await self._user_finder.by_verification_token(token)
        if user is None or user.is_email_verified():
            return False
        caduca = user.verification_token_expires_at
        if caduca is None or datetime.now() <= caduca:
            return False
        return await self._envia(user, str(user.email.value))
