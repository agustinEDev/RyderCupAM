"""
Update Security Use Case - Application Layer

Caso de uso para actualizar datos de seguridad del usuario: la contraseña, y/o pedir
un correo nuevo, que queda pendiente hasta confirmarlo desde su dirección (ADR-045).
Requiere validación de contraseña actual para autorizar los cambios.
Security Logging (v1.8.0): Registra cambios de contraseña y email.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from src.modules.user.application.dto.user_dto import (
    UpdateSecurityRequestDTO,
    UpdateSecurityResponseDTO,
    UserResponseDTO,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.domain.entities.password_history import PasswordHistory
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import (
    MENSAJES_DE_LA_CONTRASENA,
    CodigoDeContrasena,
    InvalidPasswordError,
    Password,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.logging.security_logger import get_security_logger
from src.shared.infrastructure.security.bcrypt_executor import run_bcrypt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Preparado:
    """Lo comprobado fuera de la transacción, para la fase con la fila bloqueada."""

    user_id_vo: UserId
    contrasena_leida: str | None
    nueva: Password | None


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

    async def _prepara(self, user_id: str, request: UpdateSecurityRequestDTO) -> _Preparado:
        """
        Fases 1 y 2 (BE #283): leer sin bloquear en una transacción que se cierra, y
        después, ya sin ninguna, todos los bcrypt: la contraseña actual, la política de
        la nueva (antes de calcular nada con ella), el historial y la nueva. Los errores,
        en el mismo orden de siempre: la actual, el correo ocupado y la nueva.
        """
        user_id_vo = UserId(user_id)
        async with self._uow:
            user = await self._uow.users.find_by_id(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")
            # La que se va a comprobar, guardada AHORA: si se leyera tras los bcrypt,
            # un cambio entretanto pasaría por la comprobada (test entre fases)
            leida = user.password.hashed_value if user.password else None
            historial = (
                await self._uow.password_history.find_recent_by_user(user_id_vo, limit=5)
                if request.new_password
                else []
            )
            ocupado = (
                await self._uow.users.find_by_email(Email(request.new_email))
                if request.new_email
                else None
            )

        if not await run_bcrypt(user.verify_password, request.current_password):
            raise InvalidCredentialsError("Current password is incorrect")
        if ocupado is not None and str(ocupado.id.value) != user_id:
            raise DuplicateEmailError(f"Email {request.new_email} is already in use")

        nueva = None
        if request.new_password:
            # El orden de antes: la política (barata, sin calcular), el historial, y el
            # hash de la nueva al final, para no gastarlo con una repetida
            Password.comprueba_la_politica(request.new_password)
            for registro in historial:
                anterior = Password(registro.password_hash)
                if await run_bcrypt(anterior.verify, request.new_password):
                    # Con su código (BE #519): el cliente lo reconocía buscando este
                    # texto, que va en inglés
                    raise InvalidPasswordError(
                        MENSAJES_DE_LA_CONTRASENA[CodigoDeContrasena.REUSED],
                        error_code=CodigoDeContrasena.REUSED,
                    )
            nueva = await run_bcrypt(Password.from_plain_text, request.new_password)
        return _Preparado(user_id_vo=user_id_vo, contrasena_leida=leida, nueva=nueva)

    async def _bloquea_y_comprueba(self, preparado: _Preparado) -> User:
        """Fase 3: la fila bloqueada, y la contraseña tiene que seguir siendo la que se
        comprobó. Si cambió entretanto (un restablecimiento a la vez), la que tecleó ya
        no es la actual: el mismo error que si la hubiera tecleado mal (BE #283)."""
        user = await self._uow.users.find_by_id_for_update(preparado.user_id_vo)
        if not user:
            raise UserNotFoundError(f"User with id {preparado.user_id_vo.value} not found")
        actual = user.password.hashed_value if user.password else None
        if actual != preparado.contrasena_leida:
            raise InvalidCredentialsError("Current password is incorrect")
        return user

    async def _handle_email_change(
        self, user: object, new_email: str, user_id: str
    ) -> tuple[bool, str | None]:
        """El correo nuevo queda pendiente hasta confirmarlo desde su dirección (#749)."""
        email_vo = Email(new_email)
        existing_user = await self._uow.users.find_by_email(email_vo)

        if existing_user and str(existing_user.id.value) != user_id:
            raise DuplicateEmailError(f"Email {new_email} is already in use")

        # El mismo correo que ya tiene: nada que cambiar (como antes)
        if user.email is not None and email_vo == user.email:
            return False, None
        token = user.request_email_change(new_email, ahora=datetime.now())
        return True, token

    async def _handle_password_change(
        self, user: User, nueva: Password, user_id_vo: UserId
    ) -> tuple[bool, int]:
        """La nueva (ya calculada y comprobada contra el historial, fuera de la
        transacción), al historial, y se revocan los refresh tokens."""
        user.change_password(nueva)

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

    async def _avisa_del_cambio_de_correo(self, user: object, new_email: str, token: str) -> None:
        """El enlace al correo nuevo y el aviso al de antes. Un fallo no tumba el cambio."""
        if not self._email_service:
            return
        envios = [
            (
                "confirmation",
                self._email_service.send_email_change_confirmation,
                {"to_email": new_email, "user_name": user.first_name, "token": token},
            )
        ]
        # Nunca a un correo sin confirmar (como el aviso de nuevo inicio)
        if user.email_verified:
            envios.append(
                (
                    "notice",
                    self._email_service.send_email_change_requested_notice,
                    {
                        "to_email": str(user.email.value),
                        "user_name": user.first_name,
                        "new_email": new_email,
                    },
                )
            )
        for nombre, envia, datos in envios:
            try:
                if not await envia(**datos):
                    logger.warning("Email change %s mail not sent for a user", nombre)
            except Exception as error:
                logger.error("Email change %s mail failed: %s", nombre, type(error).__name__)

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

        preparado = await self._prepara(user_id, request)

        async with self._uow:
            user = await self._bloquea_y_comprueba(preparado)
            user_id_vo = preparado.user_id_vo

            # Tracking de cambios
            email_changed = False
            password_changed = False
            tokens_revoked_count = 0
            token_del_cambio = None

            # Procesar cambio de email
            if request.new_email:
                email_changed, token_del_cambio = await self._handle_email_change(
                    user, request.new_email, user_id
                )

            # Procesar cambio de password
            if preparado.nueva is not None:
                password_changed, tokens_revoked_count = await self._handle_password_change(
                    user, preparado.nueva, user_id_vo
                )
                # Un correo pendiente que no se pide ahora, fuera: quizá lo pidió quien
                # entró con la contraseña de antes (/code-review de la rama)
                if not email_changed:
                    user.cancel_email_change()

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

        # El enlace, al correo nuevo; el aviso, al de antes
        if email_changed and token_del_cambio:
            await self._avisa_del_cambio_de_correo(user, request.new_email, token_del_cambio)

        # Construir respuesta
        return UpdateSecurityResponseDTO(
            user=UserResponseDTO.model_validate(user),
            message=(
                "Email change pending confirmation"
                if email_changed
                else "Security settings updated successfully"
            ),
        )
