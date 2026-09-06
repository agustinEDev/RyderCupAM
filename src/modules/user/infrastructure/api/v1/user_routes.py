from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.config.dependencies import (
    get_competition_uow,
    get_current_user,
    get_find_user_use_case,
    get_get_player_stats_use_case,
    get_get_recent_matches_use_case,
    get_search_users_use_case,
    get_update_profile_use_case,
    get_update_security_use_case,
)
from src.config.settings import settings
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.application.dto.player_stats_dto import (
    PlayerStatsResponseDTO,
    RecentMatchesResponseDTO,
    ScoringBreakdownResponseDTO,
)
from src.modules.user.application.dto.user_dto import (
    FindUserRequestDTO,
    FindUserResponseDTO,
    SearchUsersResponseDTO,
    UpdateProfileRequestDTO,
    UpdateProfileResponseDTO,
    UpdateSecurityRequestDTO,
    UpdateSecurityResponseDTO,
    UserResponseDTO,
    UserRolesResponseDTO,
)
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.application.use_cases.get_recent_matches_use_case import (
    GetRecentMatchesUseCase,
)
from src.modules.user.application.use_cases.search_users_use_case import SearchUsersUseCase
from src.modules.user.application.use_cases.update_profile_use_case import (
    UpdateProfileUseCase,
)
from src.modules.user.application.use_cases.update_security_use_case import (
    UpdateSecurityUseCase,
)
from src.modules.user.domain.errors.user_errors import (
    AliasAlreadyTakenError,
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
    "/search-autocomplete",
    response_model=SearchUsersResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Autocompletar busqueda de usuarios",
    description="Busca usuarios por nombre o alias parcial para autocompletado.",
    tags=["Users"],
)
async def search_users_autocomplete(
    query: str = Query(..., min_length=2, max_length=100, description="Texto de busqueda parcial"),
    use_case: SearchUsersUseCase = Depends(get_search_users_use_case),
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001
):
    """
    Endpoint de autocompletado para buscar usuarios por nombre parcial.
    Devuelve hasta 10 resultados que coincidan parcialmente con el nombre, el
    apellido o el alias. Cada resultado lleva el alias junto al nombre real:
    es lo que permite distinguir a dos jugadores parecidos.
    """
    return await use_case.execute(query)


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
    description=(
        "Actualiza la información personal del usuario autenticado: nombre, apellidos, "
        "país, género y/o alias. Devuelve 409 si el alias pedido ya lo tiene otra persona."
    ),
    tags=["Users"],
    responses={
        status.HTTP_409_CONFLICT: {"description": "El alias ya está en uso por otro usuario."},
    },
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
    - Género (gender)
    - Alias (alias) - apodo público, único entre todos los usuarios

    Al menos uno de los campos debe ser proporcionado.
    Enviar `alias` como cadena vacía lo borra y devuelve al usuario a su nombre real.
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
    except AliasAlreadyTakenError as e:
        # 409 y no 400: la petición es correcta, lo que pasa es que otra
        # persona llegó antes. El mensaje va tal cual al campo del formulario
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
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


@router.get(
    "/me/stats",
    response_model=PlayerStatsResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Estadísticas del jugador",
    description="Resumen de rendimiento del usuario actual para el panel.",
    tags=["Users"],
)
async def get_my_stats(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetPlayerStatsUseCase = Depends(get_get_player_stats_use_case),
):
    """
    Resumen agregado del jugador: hándicap, media respecto al par, rondas y
    torneos.

    Una cuenta sin historial devuelve ceros y `null`, no un 404: el panel de un
    usuario nuevo es un caso normal, no un error.

    `handicap_trend` va siempre a `null` mientras no exista histórico de
    hándicap; el campo está para no cambiar el contrato cuando lo haya.
    """
    return await use_case.execute(UserId(str(current_user.id)))


@router.get(
    "/me/stats/breakdown",
    response_model=ScoringBreakdownResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Desglose de golpes del jugador",
    description="Dónde gana y dónde pierde golpes: por par, por mitad de vuelta y por campo.",
    tags=["Users"],
)
async def get_my_scoring_breakdown(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetPlayerStatsUseCase = Depends(get_get_player_stats_use_case),
):
    """
    Desglose de golpes (BE #168).

    Va aparte de `/me/stats` y no dentro porque son bastantes datos y el panel
    no siempre los necesita. Lo que ahorra es la serialización, no el trabajo de
    base de datos: recorre las mismas vueltas que el resumen, así que una
    pantalla que pida los dos endpoints hace ese recorrido dos veces. Si algún
    día pesa, la salida es un endpoint que devuelva ambos, no cachear este.

    Mide sobre las mismas vueltas que la media, con el mismo tope de doble bogey
    neto. Una cuenta sin historial devuelve ceros y listas vacías, no un 404.
    """
    return await use_case.execute_breakdown(UserId(str(current_user.id)))


@router.get(
    "/me/stats/golf-courses/{golf_course_id}",
    response_model=PlayerStatsResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Estadísticas del jugador en un campo",
    description="Mismo resumen, restringido a las rondas jugadas en un campo concreto.",
    tags=["Users"],
)
async def get_my_stats_for_golf_course(
    golf_course_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetPlayerStatsUseCase = Depends(get_get_player_stats_use_case),
):
    """
    Desglose por campo.

    Los contadores de torneos vienen a cero: son globales del jugador y
    repetirlos dentro de un campo daría a entender que jugó ahí esos torneos.
    """
    return await use_case.execute(
        UserId(str(current_user.id)), golf_course_id=GolfCourseId(golf_course_id)
    )


@router.get(
    "/me/matches",
    response_model=RecentMatchesResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Historial de partidas del jugador",
    description="Últimas partidas del usuario, mezclando torneo y partida rápida.",
    tags=["Users"],
)
async def get_my_recent_matches(
    limit: int = Query(default=10, ge=1, le=50, description="Número de partidas a devolver"),
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetRecentMatchesUseCase = Depends(get_get_recent_matches_use_case),
):
    """
    Historial unificado, de la partida más reciente a la más antigua.

    Partidos de torneo y partidas rápidas conviven en la misma lista, y cada
    entrada deja en `null` lo que no le aplica: un partido de torneo no tiene
    `scoring_format`, y una partida libre no tiene `result` de match play.

    Las partidas que el propio jugador ocultó (#127) no aparecen aquí, pero
    siguen apareciendo en el historial de los demás participantes.
    """
    return await use_case.execute(UserId(str(current_user.id)), limit=limit)
