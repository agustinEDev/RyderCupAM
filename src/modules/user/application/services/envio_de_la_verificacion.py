"""
Envía un enlace de verificación nuevo y, solo si salió, lo guarda (fase 3, revisión).

Primero el correo y después el hash: si el proveedor falla, la cuenta conserva el enlace
de antes. Se guarda con la fila bloqueada y solo si la cuenta sigue sin verificar: si se
verificó entretanto, el enlace nuevo no hace falta.
"""

import logging

from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.reenvio_de_verificacion_port import (
    ReenvioDeVerificacion,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)

logger = logging.getLogger(__name__)


class EnvioDeLaVerificacion:
    """El envío y, después, el guardado del enlace."""

    def __init__(self, uow: UserUnitOfWorkInterface, email_service: IEmailService):
        """Con su unidad de trabajo (la suya, fuera de la petición) y el correo."""
        self._uow = uow
        self._email_service = email_service

    async def envia_y_guarda(self, datos: ReenvioDeVerificacion) -> bool:
        """
        Returns:
            True si el correo salió (y el enlace quedó guardado, si aún hacía falta)
        """
        enviado = await self._email_service.send_verification_email(
            to_email=datos.to_email, user_name=datos.user_name, verification_token=datos.token
        )
        if not enviado:
            logger.error("No se pudo enviar el email de verificación al usuario %s", datos.user_id)
            return False
        async with self._uow:
            user = await self._uow.users.find_by_id_for_update(datos.user_id)
            if user is not None and not user.is_email_verified():
                user.set_verification_token(datos.token)
                await self._uow.users.save(user)
        return True
