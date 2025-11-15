"""
Resend Verification Email Use Case - Application Layer

Caso de uso para reenviar el email de verificación a un usuario.
"""

import logging
from typing import Optional

from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.user_finder import UserFinder
from src.modules.user.domain.value_objects.email import Email
from src.shared.infrastructure.email.email_service import email_service

logger = logging.getLogger(__name__)


class ResendVerificationEmailUseCase:
    """
    Caso de uso para reenviar el email de verificación a un usuario.

    Este caso de uso orquesta el proceso de regenerar el token de verificación
    y reenviar el email al usuario que lo solicite.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)

    async def execute(self, email: str) -> bool:
        """
        Ejecuta el caso de uso de reenvío de email de verificación.

        Args:
            email: Email del usuario al que reenviar la verificación

        Returns:
            bool: True si el email se envió exitosamente

        Raises:
            ValueError: Si el email no existe o ya está verificado
        """
        if not email or email.strip() == "":
            raise ValueError("El email es requerido")

        # Primera transacción: buscar usuario y validar
        async with self._uow:
            # Buscar el usuario por email (convertir a Value Object)
            email_vo = Email(email)
            user = await self._user_finder.by_email(email_vo)

            if not user:
                raise ValueError("Si el email existe y no está verificado, se enviará un email de verificación")

            # Verificar si el email ya está verificado
            if user.is_email_verified():
                raise ValueError("Si el email existe y no está verificado, se enviará un email de verificación")

            # Generar nuevo token de verificación (solo en memoria, NO guardamos aún)
            new_token = user.generate_verification_token()

            # Extraer datos necesarios ANTES de salir del contexto
            # para evitar detached entity errors
            user_id = user.id.value
            user_name = user.get_full_name()

        # PRIMERO: Enviar email (fuera de transacción porque es síncrono)
        # Si esto falla, no se ha guardado nada en BD (no hay inconsistencia)
        email_sent = email_service.send_verification_email(
            to_email=email,
            user_name=user_name,
            verification_token=new_token
        )

        if not email_sent:
            logger.error("No se pudo enviar el email de verificación al usuario %s", user_id)
            raise ValueError("Error al enviar el email de verificación")

        # SEGUNDO: Solo si el email se envió correctamente, guardar el token en BD
        async with self._uow:
            # Re-buscar el usuario para tener una entidad attached
            user = await self._user_finder.by_email(email_vo)
            if not user:
                raise ValueError("Usuario no encontrado")

            # Regenerar el mismo token (es determinista si no ha pasado tiempo)
            # O mejor: guardamos el token que ya generamos
            user.verification_token = new_token

            await self._uow.users.save(user)
            # El context manager (__aexit__) hace commit automático

        logger.info(
            "Email de verificación reenviado correctamente al usuario %s",
            user_id
        )

        return True
