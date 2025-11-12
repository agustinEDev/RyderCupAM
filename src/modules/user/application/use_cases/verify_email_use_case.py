"""
Verify Email Use Case - Application Layer

Caso de uso para verificar el email de un usuario usando un token.
"""

import logging
from typing import Optional

from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.user_finder import UserFinder

logger = logging.getLogger(__name__)


class VerifyEmailUseCase:
    """
    Caso de uso para verificar el email de un usuario.

    Este caso de uso orquesta la verificación del email del usuario
    usando el token proporcionado.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_finder = UserFinder(self._uow.users)

    async def execute(self, token: str) -> bool:
        """
        Ejecuta el caso de uso de verificación de email.

        Args:
            token: Token de verificación del email

        Returns:
            bool: True si la verificación fue exitosa, False en caso contrario

        Raises:
            ValueError: Si el token es inválido o el usuario no existe
        """
        if not token or token.strip() == "":
            raise ValueError("El token de verificación es requerido")

        async with self._uow:
            # Buscar el usuario por token de verificación
            user = await self._user_finder.by_verification_token(token)

            if not user:
                raise ValueError("Token de verificación inválido o expirado")

            # Verificar el email en la entidad de dominio
            verification_success = user.verify_email(token)

            if not verification_success:
                raise ValueError("No se pudo verificar el email")

            # Guardar los cambios
            await self._uow.users.save(user)

            # El context manager (__aexit__) hace commit automático y publica eventos

        logger.info("Email verificado correctamente para el usuario %s", user.id.value)

        return True
