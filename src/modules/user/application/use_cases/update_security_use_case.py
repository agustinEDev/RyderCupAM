"""
Update Security Use Case - Application Layer

Caso de uso para actualizar datos de seguridad del usuario (email y/o password).
Requiere validación de contraseña actual para autorizar los cambios.
Security Logging (v1.8.0): Registra cambios de contraseña y email.
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
from src.shared.infrastructure.logging.security_logger import get_security_logger

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

    async def execute(  # noqa: PLR0912, C901 - Complexity required by OWASP security requirements
        self,
        user_id: str,
        request: UpdateSecurityRequestDTO
    ) -> UpdateSecurityResponseDTO:
        """
        Ejecuta el caso de uso de actualización de seguridad.

        Args:
            user_id: ID del usuario autenticado (del JWT token)
            request: DTO con los datos a actualizar, password actual y contexto de seguridad

        Returns:
            UpdateSecurityResponseDTO con el usuario actualizado

        Security Logging (v1.8.0):
            - Registra cambio de contraseña (severity HIGH)
            - Registra cambio de email (severity HIGH)
            - Revoca refresh tokens si cambia contraseña

        Raises:
            UserNotFoundError: Si el usuario no existe
            InvalidCredentialsError: Si la contraseña actual es incorrecta
            DuplicateEmailError: Si el nuevo email ya está en uso
            ValueError: Si los datos no son válidos

        Note:
            Complejidad necesaria por requisitos de seguridad OWASP:
            - Validación de contraseña actual
            - Verificación de email único
            - Revocación de tokens
            - Logging de seguridad diferenciado
            - Notificación por email
        """
        # Obtener security logger
        security_logger = get_security_logger()

        # Valores por defecto para security logging
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        async with self._uow:
            # Buscar usuario
            user_id_vo = UserId(user_id)
            user = await self._uow.users.find_by_id(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            # Verificar contraseña actual
            if not user.verify_password(request.current_password):
                raise InvalidCredentialsError("Current password is incorrect")

            # Tracking de cambios para security logging
            email_changed = False
            password_changed = False

            # Si se cambia el email, verificar que no esté en uso
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
                password_changed = True

                # IMPORTANTE: Si cambia contraseña, revocar todos los refresh tokens
                # Esto previene que tokens antiguos sigan siendo válidos
                refresh_tokens = await self._uow.refresh_tokens.find_all_by_user(user_id_vo)
                tokens_revoked_count = 0

                for refresh_token in refresh_tokens:
                    if not refresh_token.revoked:
                        refresh_token.revoke()
                        await self._uow.refresh_tokens.save(refresh_token)
                        tokens_revoked_count += 1

            # Si se cambió el email, generar token de verificación
            verification_token = None
            if email_changed:
                verification_token = user.generate_verification_token()

            # Guardar cambios
            await self._uow.users.save(user)

            # El context manager (__aexit__) hace commit automático y publica eventos

        # Security Logging: Cambio de contraseña
        if password_changed:
            security_logger.log_password_changed(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                old_password_verified=True,
            )

            # Security Logging: Revocación de tokens por cambio de contraseña
            if tokens_revoked_count > 0:
                security_logger.log_refresh_token_revoked(
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    tokens_revoked_count=tokens_revoked_count,
                    reason="password_change",
                )

        # Security Logging: Cambio de email
        if email_changed:
            security_logger.log_email_changed(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                email_verification_required=True,
            )

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
