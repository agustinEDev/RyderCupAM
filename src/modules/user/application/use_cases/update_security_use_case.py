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
from src.modules.user.domain.entities.password_history import PasswordHistory
from src.modules.user.domain.errors.user_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.logging.security_logger import get_security_logger

logger = logging.getLogger(__name__)


class UpdateSecurityUseCase:
    """
    Caso de uso: Actualizar datos de seguridad del usuario.

    Permite a un usuario autenticado actualizar su email y/o password,
    requiriendo verificación de la contraseña actual.
    """

    def __init__(self, uow: UserUnitOfWorkInterface, email_service: IEmailService | None = None):
        """
        Inicializa el caso de uso con sus dependencias.

        Args:
            uow: Unit of Work para manejar transacciones
            email_service: Servicio para envío de emails de verificación
        """
        self._uow = uow
        self._email_service = email_service

    async def _validate_user_and_password(
        self, user_id: str, current_password: str
    ) -> tuple[UserId, object]:
        """Valida que el usuario exista y la contraseña sea correcta."""
        user_id_vo = UserId(user_id)
        user = await self._uow.users.find_by_id(user_id_vo)

        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found")

        if not user.verify_password(current_password):
            raise InvalidCredentialsError("Current password is incorrect")

        return user_id_vo, user

    async def _handle_email_change(
        self, user: object, new_email: str, user_id: str
    ) -> tuple[bool, str | None]:
        """Maneja el cambio de email y genera token de verificación."""
        email_vo = Email(new_email)
        existing_user = await self._uow.users.find_by_email(email_vo)

        if existing_user and str(existing_user.id.value) != user_id:
            raise DuplicateEmailError(f"Email {new_email} is already in use")

        user.change_email(new_email)
        verification_token = user.generate_verification_token()
        return True, verification_token

    async def _handle_password_change(
        self, user: object, new_password: str, user_id_vo: UserId
    ) -> tuple[bool, int]:
        """Maneja el cambio de password, valida historial y revoca refresh tokens."""
        # Validar que la nueva contraseña no esté en el historial (últimas 5)
        recent_history = await self._uow.password_history.find_recent_by_user(user_id_vo, limit=5)

        # Verificar si la nueva contraseña coincide con alguna del historial
        for history_record in recent_history:
            temp_password = Password(history_record.password_hash)
            if temp_password.verify(new_password):
                raise ValueError(
                    "Cannot reuse any of your last 5 passwords. Please choose a different password."
                )

        # Cambiar la contraseña
        user.change_password(new_password)

        # Guardar el nuevo hash en el historial
        total_history_count = await self._uow.password_history.count_by_user(user_id_vo) + 1
        password_history = PasswordHistory.create(
            user_id=user_id_vo,
            password_hash=user.password.hashed_value,
            total_history_count=total_history_count,
        )
        await self._uow.password_history.save(password_history)

        # Revocar todos los refresh tokens
        refresh_tokens = await self._uow.refresh_tokens.find_all_by_user(user_id_vo)
        tokens_revoked_count = 0

        for refresh_token in refresh_tokens:
            if not refresh_token.revoked:
                refresh_token.revoke()
                await self._uow.refresh_tokens.save(refresh_token)
                tokens_revoked_count += 1

        return True, tokens_revoked_count

    def _log_security_changes(
        self,
        password_changed: bool,
        email_changed: bool,
        tokens_revoked_count: int,
        user_id: str,
        ip_address: str,
        user_agent: str,
        security_logger,
    ) -> None:
        """Registra los cambios de seguridad en el audit trail."""
        if password_changed:
            security_logger.log_password_changed(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                old_password_verified=True,
            )

            if tokens_revoked_count > 0:
                security_logger.log_refresh_token_revoked(
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    tokens_revoked_count=tokens_revoked_count,
                    reason="password_change",
                )

        if email_changed:
            security_logger.log_email_changed(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                email_verification_required=True,
            )

    def _send_verification_email(
        self, user: object, new_email: str, verification_token: str
    ) -> None:
        """Envía email de verificación al nuevo correo."""
        if not self._email_service:
            return

        try:
            email_sent = self._email_service.send_verification_email(
                to_email=new_email,
                user_name=user.first_name,
                verification_token=verification_token,
            )
            if not email_sent:
                logger.warning(
                    "No se pudo enviar el email de verificación para el usuario %s",
                    user.id.value,
                )
        except (requests.RequestException, ValueError, ConnectionError):
            logger.exception(
                "Error al enviar email de verificación para el usuario %s",
                user.id.value,
            )

    async def execute(
        self, user_id: str, request: UpdateSecurityRequestDTO
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
        """
        # Obtener security logger
        security_logger = get_security_logger()

        # Valores por defecto para security logging
        ip_address = request.ip_address or "unknown"
        user_agent = request.user_agent or "unknown"

        async with self._uow:
            # Validar usuario y contraseña actual
            user_id_vo, user = await self._validate_user_and_password(
                user_id, request.current_password
            )

            # Tracking de cambios
            email_changed = False
            password_changed = False
            tokens_revoked_count = 0
            verification_token = None

            # Procesar cambio de email
            if request.new_email:
                email_changed, verification_token = await self._handle_email_change(
                    user, request.new_email, user_id
                )

            # Procesar cambio de password
            if request.new_password:
                password_changed, tokens_revoked_count = await self._handle_password_change(
                    user, request.new_password, user_id_vo
                )

            # Guardar cambios
            await self._uow.users.save(user)
            # El context manager (__aexit__) hace commit automático y publica eventos

        # Security Logging
        self._log_security_changes(
            password_changed,
            email_changed,
            tokens_revoked_count,
            user_id,
            ip_address,
            user_agent,
            security_logger,
        )

        # Enviar email de verificación si cambió el email
        if email_changed and verification_token:
            self._send_verification_email(user, request.new_email, verification_token)

        # Construir respuesta
        return UpdateSecurityResponseDTO(
            user=UserResponseDTO.model_validate(user),
            message="Security settings updated successfully",
        )
