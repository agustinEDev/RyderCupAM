"""Caso de Uso: Editar un usuario (panel de administración)."""

from datetime import datetime

from src.modules.user.application.dto.admin_dto import (
    AdminUpdateUserRequestDTO,
    AdminUserSummaryDTO,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.services.avisa_del_cambio_de_correo import (
    avisa_del_cambio_de_correo,
)
from src.modules.user.domain.errors.user_errors import DuplicateEmailError, UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId


class AdminUpdateUserUseCase:
    """Edita los datos de un usuario desde el panel de administración (solo Admin)."""

    def __init__(self, uow: UserUnitOfWorkInterface, *, email_service: IEmailService):
        self._uow = uow
        # El cambio de correo queda pendiente, con su enlace y su aviso (BE #753)
        self._email_service = email_service

    async def execute(
        self, user_id_str: str, request: AdminUpdateUserRequestDTO
    ) -> AdminUserSummaryDTO:
        """
        Edita un usuario con su fila bloqueada. Un correo nuevo queda pendiente hasta
        que el usuario lo confirme (BE #753), con su enlace y su aviso tras guardar.

        Raises:
            UserNotFoundError: si no existe
            DuplicateEmailError: si otra cuenta ya usa ese correo
        """
        user_id = UserId(user_id_str)

        token_del_cambio: str | None = None
        async with self._uow:
            # Con la fila bloqueada: el cambio de correo compite con el del propio usuario
            user = await self._uow.users.find_by_id_for_update(user_id)
            if not user:
                raise UserNotFoundError(f"User not found: {user_id_str}")

            if (
                request.first_name is not None
                or request.last_name is not None
                or request.country_code is not None
            ):
                user.update_profile(
                    first_name=request.first_name,
                    last_name=request.last_name,
                    country_code_str=request.country_code,
                )

            # Sin distinguir mayúsculas: el mismo correo escrito de otra forma no es un
            # cambio, y lanzaría «es el mismo que el actual» sin guardar lo demás
            if request.email is not None and str(request.email).lower() != str(user.email).lower():
                new_email_str = str(request.email)
                existing = await self._uow.users.find_by_email(Email(new_email_str))
                if existing and existing.id != user.id:
                    raise DuplicateEmailError(f"Email {new_email_str} is already in use")
                # Pendiente hasta que el usuario lo confirme desde esa dirección, con su
                # sesión: una errata del admin no da la cuenta a quien tenga ese correo
                token_del_cambio = user.request_email_change(new_email_str, ahora=datetime.now())

            if request.handicap is not None:
                user.update_handicap(request.handicap)

            if request.is_admin is not None and request.is_admin != user.is_admin:
                user.set_is_admin(request.is_admin)

            await self._uow.users.save(user)
            last_login_map = await self._uow.user_devices.find_last_login_map(
                [uid] if (uid := user.id) is not None else []
            )

        if token_del_cambio is not None and request.email is not None:
            await avisa_del_cambio_de_correo(
                self._email_service, user, str(request.email), token_del_cambio
            )

        return AdminUserSummaryDTO(
            id=user.id.value,
            first_name=user.first_name,
            last_name=user.last_name,
            alias=user.alias,
            email=str(user.email),
            handicap=float(user.handicap) if user.handicap is not None else None,
            is_admin=user.is_admin,
            is_active=user.is_active,
            email_verified=user.email_verified,
            pending_email=user.pending_email,
            created_at=user.created_at,
            last_login_at=last_login_map.get(str(user.id.value)),
        )
