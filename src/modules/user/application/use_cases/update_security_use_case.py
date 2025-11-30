"""
Update Security Use Case - Application Layer

Caso de uso para actualizar datos de seguridad del usuario (email y/o password).
Requiere validación de contraseña actual para autorizar los cambios.
"""

import logging

import requests

from src.modules.user.application.dto.user_dto import (
    UpdateSecurityRequestDTO,
    UpdateSecurityResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.domain.errors.user_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import UserUnitOfWorkInterface
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class UpdateSecurityUseCase:
    """
    Caso de uso: Actualizar datos de seguridad del usuario.

    Permite a un usuario autenticado actualizar su email y/o password,
    requiriendo verificación de la contraseña actual.
    """

    def __init__(
        self,
        uow: UserUnitOfWorkInterface,
        email_service: IEmailService | None = None
    ):
        """
        Inicializa el caso de uso con sus dependencias.

        Args:
            uow: Unit of Work para manejar transacciones
            email_service: Servicio para envío de emails de verificación
        """
        self._uow = uow
        self._email_service = email_service

    async def execute(self, user_id: str, request: UpdateSecurityRequestDTO) -> UpdateSecurityResponseDTO:
        """
        Ejecuta el caso de uso de actualización de seguridad.

        Args:
            user_id: ID del usuario autenticado (del JWT token)
            request: DTO con los datos a actualizar y password actual

        Returns:
            UpdateSecurityResponseDTO con el usuario actualizado

        Raises:
            UserNotFoundError: Si el usuario no existe
            InvalidCredentialsError: Si la contraseña actual es incorrecta
            DuplicateEmailError: Si el nuevo email ya está en uso
            ValueError: Si los datos no son válidos
        """
        async with self._uow:
            # Buscar usuario
            user_id_vo = UserId(user_id)
            user = await self._uow.users.find_by_id(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            # Verificar contraseña actual
            if not user.verify_password(request.current_password):
                raise InvalidCredentialsError("Current password is incorrect")

            # Si se cambia el email, verificar que no esté en uso
            email_changed = False
            if request.new_email:
                email_vo = Email(request.new_email)
                existing_user = await self._uow.users.find_by_email(email_vo)
                if existing_user and str(existing_user.id.value) != user_id:
                    raise DuplicateEmailError(f"Email {request.new_email} is already in use")

                user.change_email(request.new_email)
                email_changed = True

            # Si se cambia el password
            if request.new_password:
                user.change_password(request.new_password)

            # Si se cambió el email, generar token de verificación
            verification_token = None
            if email_changed:
                verification_token = user.generate_verification_token()

            # Guardar cambios
            await self._uow.users.save(user)

            # El context manager (__aexit__) hace commit automático y publica eventos

        # Si se cambió el email, enviar email de verificación al NUEVO correo
        if email_changed and verification_token and self._email_service:
            try:
                email_sent = self._email_service.send_verification_email(
                    to_email=request.new_email,
                    user_name=user.first_name,
                    verification_token=verification_token
                )
                if not email_sent:
                    logger.warning(
                        "No se pudo enviar el email de verificación para el usuario %s",
                        user.id.value
                    )
            except (requests.RequestException, ValueError, ConnectionError):
                logger.exception(
                    "Error al enviar email de verificación para el usuario %s",
                    user.id.value
                )
                # No fallar la actualización si el email no se pudo enviar

        # Construir respuesta
        return UpdateSecurityResponseDTO(
            user=UserResponseDTO.model_validate(user),
            message="Security settings updated successfully"
        )
