"""Caso de Uso: Editar un usuario (panel de administración)."""

from src.modules.user.application.dto.admin_dto import (
    AdminUpdateUserRequestDTO,
    AdminUserSummaryDTO,
)
from src.modules.user.domain.errors.user_errors import DuplicateEmailError, UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.user_id import UserId


class AdminUpdateUserUseCase:
    """Edita los datos de un usuario desde el panel de administración (solo Admin)."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(
        self, user_id_str: str, request: AdminUpdateUserRequestDTO
    ) -> AdminUserSummaryDTO:
        user_id = UserId(user_id_str)

        async with self._uow:
            user = await self._uow.users.find_by_id(user_id)
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

            if request.email is not None and str(request.email) != str(user.email):
                new_email_str = str(request.email)
                existing = await self._uow.users.find_by_email(Email(new_email_str))
                if existing and existing.id != user.id:
                    raise DuplicateEmailError(f"Email {new_email_str} is already in use")
                user.change_email(new_email_str)

            if request.handicap is not None:
                user.update_handicap(request.handicap)

            if request.is_admin is not None and request.is_admin != user.is_admin:
                user.set_is_admin(request.is_admin)

            await self._uow.users.save(user)
            last_login_map = await self._uow.user_devices.find_last_login_map(
                [uid] if (uid := user.id) is not None else []
            )

        return AdminUserSummaryDTO(
            id=user.id.value,
            first_name=user.first_name,
            last_name=user.last_name,
            email=str(user.email),
            handicap=float(user.handicap) if user.handicap is not None else None,
            is_admin=user.is_admin,
            is_active=user.is_active,
            email_verified=user.email_verified,
            created_at=user.created_at,
            last_login_at=last_login_map.get(str(user.id.value)),
        )
