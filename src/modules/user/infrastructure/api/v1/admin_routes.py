"""
Admin Panel Routes - API Layer.

Endpoints exclusivos de administrador para gestionar usuarios y consultar
estadisticas globales de la plataforma. Todos los endpoints requieren
autenticacion + require_admin().
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.config.dependencies import (
    get_admin_delete_user_use_case,
    get_admin_list_users_use_case,
    get_admin_set_user_active_use_case,
    get_admin_update_user_use_case,
    get_current_user,
    get_get_admin_stats_use_case,
)
from src.modules.user.application.dto.admin_dto import (
    AdminListUsersRequestDTO,
    AdminListUsersResponseDTO,
    AdminSetUserActiveRequestDTO,
    AdminStatsResponseDTO,
    AdminUpdateUserRequestDTO,
    AdminUserSummaryDTO,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.use_cases.admin_delete_user_use_case import (
    AdminDeleteUserUseCase,
)
from src.modules.user.application.use_cases.admin_list_users_use_case import (
    AdminListUsersUseCase,
)
from src.modules.user.application.use_cases.admin_set_user_active_use_case import (
    AdminSetUserActiveUseCase,
)
from src.modules.user.application.use_cases.admin_update_user_use_case import (
    AdminUpdateUserUseCase,
)
from src.modules.user.application.use_cases.get_admin_stats_use_case import (
    GetAdminStatsUseCase,
)
from src.modules.user.domain.errors.user_errors import DuplicateEmailError, UserNotFoundError
from src.modules.user.domain.exceptions import UserHasActivityException
from src.shared.infrastructure.security.authorization import require_admin

router = APIRouter()


@router.get(
    "/stats",
    response_model=AdminStatsResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Estadisticas globales de la plataforma (Admin)",
)
async def get_admin_stats(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetAdminStatsUseCase = Depends(get_get_admin_stats_use_case),
):
    require_admin(current_user)
    return await use_case.execute()


@router.get(
    "/users",
    response_model=AdminListUsersResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios (Admin)",
)
async def list_users(
    search: str | None = Query(default=None),
    is_admin_filter: bool | None = Query(default=None, alias="is_admin"),
    is_active: bool | None = Query(default=None),
    email_verified: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: AdminListUsersUseCase = Depends(get_admin_list_users_use_case),
):
    require_admin(current_user)
    request = AdminListUsersRequestDTO(
        search=search,
        is_admin=is_admin_filter,
        is_active=is_active,
        email_verified=email_verified,
        limit=limit,
        offset=offset,
    )
    return await use_case.execute(request)


@router.put(
    "/users/{user_id}",
    response_model=AdminUserSummaryDTO,
    status_code=status.HTTP_200_OK,
    summary="Editar un usuario (Admin)",
)
async def update_user(
    user_id: str,
    body: AdminUpdateUserRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: AdminUpdateUserUseCase = Depends(get_admin_update_user_use_case),
):
    require_admin(current_user)
    try:
        return await use_case.execute(user_id, body)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DuplicateEmailError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put(
    "/users/{user_id}/active",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Activar o desactivar una cuenta (Admin)",
)
async def set_user_active(
    user_id: str,
    body: AdminSetUserActiveRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: AdminSetUserActiveUseCase = Depends(get_admin_set_user_active_use_case),
):
    require_admin(current_user)
    try:
        await use_case.execute(user_id, body.is_active, actor_user_id=str(current_user.id))
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrado definitivo de una cuenta (Admin)",
    description=(
        "Borra la cuenta permanentemente. Bloqueado (409) si el usuario ha creado "
        "competiciones/partidas rapidas, solicitado campos de golf, o tiene scores "
        "registrados - en ese caso, usar /active para desactivar en su lugar."
    ),
)
async def delete_user(
    user_id: str,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: AdminDeleteUserUseCase = Depends(get_admin_delete_user_use_case),
):
    require_admin(current_user)
    if user_id == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot delete their own account",
        )
    try:
        await use_case.execute(user_id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except UserHasActivityException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
