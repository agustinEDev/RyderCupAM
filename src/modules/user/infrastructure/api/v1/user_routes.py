from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.config.dependencies import (
    get_competition_uow,
    get_current_user,
    get_find_user_use_case,
    get_update_profile_use_case,
    get_update_security_use_case,
)
from src.config.settings import settings
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.application.dto.user_dto import (
    FindUserRequestDTO,
    FindUserResponseDTO,
    UpdateProfileRequestDTO,
    UpdateProfileResponseDTO,
    UpdateSecurityRequestDTO,
    UpdateSecurityResponseDTO,
    UserResponseDTO,
    UserRolesResponseDTO,
)
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.update_profile_use_case import (
    UpdateProfileUseCase,
)
from src.modules.user.application.use_cases.update_security_use_case import (
    UpdateSecurityUseCase,
)
from src.modules.user.domain.errors.user_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.infrastructure.http.http_context_validator import (
    get_trusted_client_ip,
    get_user_agent,
)
from src.shared.infrastructure.security.authorization import (
    is_admin,
    is_creator_of,
    is_player_in,
)

router = APIRouter()


# ============================================================================
# HELPER FUNCTIONS - Removed (v1.13.1)
# ============================================================================
# NOTA: get_client_ip() y get_user_agent() movidas a helper centralizado
# src/shared/infrastructure/http/http_context_validator.py
# Ahora se usa get_trusted_client_ip() para prevenir IP spoofing
# ============================================================================


@router.get(
    "/search",
    response_model=FindUserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Buscar usuario",
    description="Busca un usuario por email o nombre completo y devuelve su ID y datos básicos.",
    tags=["Users"],
)
async def find_user(
    email: str | None = Query(None, description="Email del usuario a buscar"),
    full_name: str | None = Query(None, description="Nombre completo del usuario a buscar"),
    use_case: FindUserUseCase = Depends(get_find_user_use_case),
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001
):
    """
    Endpoint para buscar un usuario por email o nombre completo.

    Permite encontrar usuarios utilizando:
    - Email: Búsqueda exacta por dirección de correo electrónico
    - Nombre completo: Búsqueda por nombre y apellidos

    Al menos uno de los dos parámetros debe ser proporcionado.
    """
    try:
        # Validar que al menos un parámetro sea proporcionado
        if not email and not full_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe proporcionar al menos 'email' o 'full_name' para la búsqueda.",
            )

        # Crear el DTO de request
        request = FindUserRequestDTO(email=email, full_name=full_name)

        # Ejecutar el caso de uso
        return await use_case.execute(request)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/profile",
    response_model=UpdateProfileResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar perfil del usuario",
    description="Actualiza la información personal del usuario autenticado (nombre, apellidos y/o país).",
    tags=["Users"],
)
async def update_profile(
    request: UpdateProfileRequestDTO,
    use_case: UpdateProfileUseCase = Depends(get_update_profile_use_case),
    current_user: UserResponseDTO = Depends(get_current_user),
):
    """
    Endpoint para actualizar información personal del usuario.

    Permite al usuario autenticado actualizar:
    - Nombre (first_name)
    - Apellidos (last_name)
    - Código de país (country_code) - ISO 3166-1 alpha-2

    Al menos uno de los campos debe ser proporcionado.
    NO requiere contraseña actual (solo autenticación JWT).
    """
    try:
        # Ejecutar el caso de uso con el user_id del token JWT
        user_id = str(current_user.id)
        response = await use_case.execute(user_id, request)
        return response

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/security",
    response_model=UpdateSecurityResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar datos de seguridad",
    description="Actualiza el email y/o password del usuario autenticado. Requiere contraseña actual.",
    tags=["Users"],
)
async def update_security(
    http_request: Request,
    request: UpdateSecurityRequestDTO,
    use_case: UpdateSecurityUseCase = Depends(get_update_security_use_case),
    current_user: UserResponseDTO = Depends(get_current_user),
):
    """
    Endpoint para actualizar datos de seguridad del usuario.

    Permite al usuario autenticado actualizar:
    - Email (new_email)
    - Password (new_password + confirm_password)

    REQUIERE:
    - current_password: Contraseña actual para verificación
    - Al menos uno de: new_email o new_password

    Si se cambia password, se debe proporcionar confirm_password.

    Security Logging (v1.8.0):
    - Registra cambios de contraseña (severity HIGH)
    - Registra cambios de email (severity HIGH)
    - Revoca refresh tokens si cambia contraseña
    """
    try:
        # Security Logging (v1.8.0): Extraer contexto HTTP para audit trail
        # SEGURIDAD: Usa get_trusted_client_ip() para prevenir IP spoofing
        request.ip_address = get_trusted_client_ip(http_request, settings.TRUSTED_PROXIES)
        request.user_agent = get_user_agent(http_request)

        # Ejecutar el caso de uso con el user_id del token JWT
        user_id = str(current_user.id)
        response = await use_case.execute(user_id, request)
        return response

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e
    except DuplicateEmailError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/me/roles/{competition_id}",
    response_model=UserRolesResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Consultar roles del usuario en una competición",
    description="Retorna los roles del usuario actual en una competición específica (admin, creator, player).",
    tags=["Users"],
)
async def get_my_roles_in_competition(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """
    Endpoint para consultar los roles del usuario actual en una competición.

    **Roles retornados:**
    - `is_admin`: Usuario es administrador del sistema (rol global)
    - `is_creator`: Usuario creó esta competición (rol contextual)
    - `is_player`: Usuario está enrollado con status APPROVED (rol contextual)

    **Casos de uso (Frontend):**
    - Mostrar/ocultar botón "Editar Competición" (solo creator o admin)
    - Mostrar/ocultar botón "Gestionar Inscripciones" (solo creator o admin)
    - Mostrar/ocultar botón "Anotar Scores" (solo players)
    - Mostrar badge "Admin" o "Creator" en UI

    **Seguridad:**
    - Solo el usuario autenticado puede consultar sus propios roles
    - La autorización real se valida en backend (este endpoint es solo para UX)

    **Returns:**
    - Objeto con flags de roles (is_admin, is_creator, is_player)
    """
    try:
        competition_vo_id = CompetitionId(competition_id)
        user_vo_id = UserId(str(current_user.id))

        # Obtener la competición para validar que existe y verificar creator
        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)

            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Competition with id {competition_id} not found",
                )

            # Verificar roles usando authorization helpers
            user_is_admin = is_admin(current_user)
            user_is_creator = is_creator_of(current_user, competition)
            user_is_player = await is_player_in(user_vo_id, competition_vo_id, uow)

            return UserRolesResponseDTO(
                is_admin=user_is_admin,
                is_creator=user_is_creator,
                is_player=user_is_player,
                competition_id=str(competition_id),
            )

    except HTTPException:
        # Re-raise HTTPExceptions (404, etc.)
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid competition ID format: {e!s}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}",
        ) from e
