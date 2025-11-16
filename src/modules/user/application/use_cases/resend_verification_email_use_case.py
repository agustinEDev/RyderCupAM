"""
Resend Verification Email Use Case - Application Layer

Caso de uso para reenviar el email de verificación a un usuario.
"""

import logging
import secrets
from typing import Optional

from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.user_finder import UserFinder
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.application.ports.email_service_interface import IEmailService

logger = logging.getLogger(__name__)


class ResendVerificationError(ValueError):
    """Exception raised when resend verification fails due to security constraints."""
    pass


# Generic error message to prevent user enumeration
GENERIC_ERROR_MESSAGE = "Si el email existe y no está verificado, se enviará un email de verificación"


class ResendVerificationEmailUseCase:
    """
    Caso de uso para reenviar el email de verificación a un usuario.

    Este caso de uso orquesta el proceso de regenerar el token de verificación
    y reenviar el email al usuario que lo solicite.
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        email_service: Optional[IEmailService] = None
    ):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)
        self._email_service = email_service

    async def execute(self, email: str) -> bool:
        """
        Ejecuta el caso de uso de reenvío de email de verificación.

        Args:
            email: Email del usuario al que reenviar la verificación

        Returns:
            bool: True si el email se envió exitosamente

        Raises:
            ResendVerificationError: Si el email no existe o ya está verificado
        """
        if not email or email.strip() == "":
            raise ResendVerificationError("El email es requerido")

        # Primera transacción: SOLO LECTURA - buscar usuario y validar
        async with self._uow:
            # Buscar el usuario por email (convertir a Value Object)
            email_vo = Email(email)
            user = await self._user_finder.by_email(email_vo)

            if not user:
                raise ResendVerificationError(GENERIC_ERROR_MESSAGE)

            # Verificar si el email ya está verificado
            if user.is_email_verified():
                raise ResendVerificationError(GENERIC_ERROR_MESSAGE)

            # Extraer datos necesarios ANTES de salir del contexto
            # para evitar detached entity errors
            user_id = user.id.value
            user_name = user.get_full_name()

        # FUERA DE TRANSACCIÓN: Generar token sin mutar entidad
        verification_token = secrets.token_urlsafe(32)

        # PRIMERO: Enviar email (fuera de transacción porque es síncrono)
        # Si esto falla, no se ha guardado nada en BD (no hay inconsistencia)
        if not self._email_service:
            logger.error("Email service no está disponible")
            raise ResendVerificationError("Servicio de email no disponible")

        email_sent = self._email_service.send_verification_email(
            to_email=email,
            user_name=user_name,
            verification_token=verification_token
        )

        if not email_sent:
            logger.error("No se pudo enviar el email de verificación al usuario %s", user_id)
            raise ResendVerificationError("Error al enviar el email de verificación")

        # SEGUNDO: Solo si el email se envió correctamente, guardar el token en BD
        async with self._uow:
            # Re-buscar el usuario para tener una entidad attached y evitar race conditions
            user = await self._user_finder.by_email(email_vo)
            if not user:
                raise ResendVerificationError(GENERIC_ERROR_MESSAGE)

            # Verificar nuevamente que no esté verificado (evitar race conditions)
            if user.is_email_verified():
                raise ResendVerificationError(GENERIC_ERROR_MESSAGE)

            # Asignar el token generado fuera de transacción
            user.verification_token = verification_token

            await self._uow.users.save(user)
            # El context manager (__aexit__) hace commit automático

        logger.info(
            "Email de verificación reenviado correctamente al usuario %s",
            user_id
        )

        return True
