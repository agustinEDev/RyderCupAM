"""
Confirm Email Change Use Case - Application Layer

Confirma el correo nuevo pendiente con el token del enlace que llegó a esa dirección
(#749). Solo desde la sesión de la cuenta: un desconocido que reciba el enlace por un
error al escribir el correo no puede confirmarlo.
"""

import logging
from collections.abc import Callable
from datetime import datetime

from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.services.registra_sin_romper import registra_sin_romper
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.exceptions import (
    EmailChangeEmailInUseError,
    EmailChangeExpiredError,
    EmailChangeInvalidError,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class ConfirmEmailChangeUseCase:
    """Confirma el cambio de correo pendiente de la cuenta con sesión."""

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        reloj: Callable[[], datetime] = datetime.now,
        *,
        security_audit: ISecurityAuditLogger,
        email_service: IEmailService,
    ):
        """El caso de uso, con su reloj (para los tests de la caducidad)."""
        self._security_audit = security_audit
        self._email_service = email_service
        self._uow = uow
        self._reloj = reloj

    async def execute(
        self,
        user_id: str,
        token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserResponseDTO:
        """
        Confirma el cambio, con la fila bloqueada (tabla de caminos de #749).

        Raises:
            EmailChangeInvalidError: si no hay ese cambio pendiente
            EmailChangeExpiredError: si caducó (queda anulado)
            EmailChangeEmailInUseError: si otra cuenta tiene ya ese correo (anulado)
        """
        ahora = self._reloj()
        anulado: Exception | None = None
        async with self._uow:
            user = await self._uow.users.find_by_id_for_update(UserId(user_id))
            if user is None:
                raise UserNotFoundError(f"User not found: {user_id}")
            # El token, antes que nada: con otro, ni se anula ni se dice si está ocupado
            if not user.pending_email_token_matches(token):
                raise EmailChangeInvalidError("No pending email change with that token")
            # El de antes, para avisarle; solo si estaba verificado (como el aviso al
            # pedirlo: nunca a un correo sin confirmar)
            antes = str(user.email.value) if user.email_verified else None
            pendiente = user.pending_email_at(ahora)
            if pendiente is not None:
                otra = await self._uow.users.find_by_email(Email(pendiente))
                if otra is not None and otra.id != user.id:
                    anulado = EmailChangeEmailInUseError("Email already in use")
            if anulado is None:
                try:
                    user.confirm_email_change(token, ahora=ahora)
                except EmailChangeExpiredError as caducado:
                    anulado = caducado
            if anulado is not None:
                # El cambio se anula y SE GUARDA: lanzar dentro de la transacción la
                # desharía
                user.cancel_email_change()
            await self._uow.users.save(user)
        if anulado is not None:
            raise anulado
        # El cambio de verdad, al log (el de la petición dice «pendiente»). Un fallo
        # del log no deshace el cambio
        registra_sin_romper(
            "Email change",
            lambda: self._security_audit.log_email_changed(
                user_id=user_id,
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown",
                email_verification_required=False,
            ),
        )
        if antes is not None:
            await self._avisa_al_de_antes(antes, user.first_name, str(user.email.value))
        return UserResponseDTO.model_validate(user)

    async def _avisa_al_de_antes(self, antes: str, nombre: str, nuevo: str) -> None:
        """El aviso al correo de antes (BE #753). Si falla, el cambio ya está hecho."""
        try:
            enviado = await self._email_service.send_email_changed_notice(
                to_email=antes, user_name=nombre, new_email=nuevo
            )
        except Exception as error:
            logger.error("Email changed notice failed: %s", type(error).__name__)
            return
        if not enviado:
            logger.error("Email changed notice was not sent")
