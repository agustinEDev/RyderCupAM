"""Caso de Uso: Listar usuarios (panel de administración)."""

from src.modules.user.application.dto.admin_dto import (
    AdminListUsersRequestDTO,
    AdminListUsersResponseDTO,
    AdminUserSummaryDTO,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)


class AdminListUsersUseCase:
    """Lista usuarios paginados, opcionalmente filtrados por búsqueda (solo Admin)."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, request: AdminListUsersRequestDTO) -> AdminListUsersResponseDTO:
        async with self._uow:
            users = await self._uow.users.find_all(
                limit=request.limit,
                offset=request.offset,
                search=request.search,
                is_admin=request.is_admin,
                is_active=request.is_active,
                email_verified=request.email_verified,
            )
            total_count = await self._uow.users.count_all(
                search=request.search,
                is_admin=request.is_admin,
                is_active=request.is_active,
                email_verified=request.email_verified,
            )

        return AdminListUsersResponseDTO(
            users=[
                AdminUserSummaryDTO(
                    id=user.id.value,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    email=str(user.email),
                    handicap=float(user.handicap) if user.handicap is not None else None,
                    is_admin=user.is_admin,
                    is_active=user.is_active,
                    email_verified=user.email_verified,
                    created_at=user.created_at,
                )
                for user in users
            ],
            total_count=total_count,
            limit=request.limit,
            offset=request.offset,
        )
