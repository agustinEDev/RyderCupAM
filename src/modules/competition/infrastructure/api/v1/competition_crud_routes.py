"""Competition CRUD Routes - Create, Read, Update, Delete endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.config.dependencies import (
    get_competition_uow,
    get_create_competition_use_case,
    get_current_user,
    get_delete_competition_use_case,
    get_get_competition_use_case,
    get_list_competitions_use_case,
    get_uow,
    get_update_competition_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.competition_dto import (
    CompetitionResponseDTO,
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
    DeleteCompetitionRequestDTO,
    UpdateCompetitionRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.mappers.competition_mapper import (
    CompetitionDTOMapper,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CompetitionAlreadyExistsError,
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    CompetitionNotDeletableError,
    DeleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    CompetitionNotEditableError,
    CompetitionNotFoundError as UpdateNotFoundError,
    NotCompetitionCreatorError as UpdateNotCreatorError,
    UpdateCompetitionUseCase,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.location_builder import InvalidCountryError
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Aliases for shared exceptions
DeleteNotFoundError = CompetitionNotFoundError
DeleteNotCreatorError = NotCompetitionCreatorError
GetNotFoundError = CompetitionNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================================================================================
# HELPER FUNCTIONS (for list endpoint)
# ======================================================================================


def _sanitize_creator_id(creator_id: str | None) -> str | None:
    if creator_id and creator_id not in ("undefined", "null", ""):
        return creator_id
    return None


async def _fetch_competitions_by_status(
    use_case, status_filter, creator_id, search_name, search_creator
):
    """Obtiene competiciones aplicando filtros de status (soporte para lista o string único)."""
    if isinstance(status_filter, list) and len(status_filter) > 0:
        all_competitions = []
        for comp_status in status_filter:
            comps = await use_case.execute(
                status=comp_status,
                creator_id=creator_id,
                search_name=search_name,
                search_creator=search_creator,
            )
            all_competitions.extend(comps)
        return list({c.id: c for c in all_competitions}.values())

    return await use_case.execute(
        status=status_filter if not isinstance(status_filter, list) else None,
        creator_id=creator_id,
        search_name=search_name,
        search_creator=search_creator,
    )


def _should_exclude_enrollment(enrollment_status, competition_status):
    """Determina si una competición inscrita debe excluirse de los resultados."""
    return enrollment_status == EnrollmentStatus.REJECTED and competition_status != "ACTIVE"


def _matches_status_filter(competition_status, status_filter):
    """Verifica si una competición cumple con el filtro de status."""
    if not status_filter:
        return True
    if isinstance(status_filter, list):
        return competition_status in [s.upper() for s in status_filter]
    return competition_status == status_filter.upper()


async def _fetch_enrolled_competitions(
    uow, enrollments, created_competition_ids, status_filter, enrollment_status_map
):
    """Obtiene las competiciones donde el usuario está inscrito (excluyendo las que ya creó)."""
    enrolled_competition_ids = {enrollment.competition_id for enrollment in enrollments}
    enrolled_competitions = []

    for comp_id in enrolled_competition_ids:
        competition = await uow.competitions.find_by_id(comp_id)

        if not competition or competition.id in created_competition_ids:
            continue

        enrollment_status = enrollment_status_map.get(competition.id)

        if _should_exclude_enrollment(enrollment_status, competition.status.value):
            continue

        if _matches_status_filter(competition.status.value, status_filter):
            enrolled_competitions.append(competition)

    return enrolled_competitions


async def _get_user_competitions(
    uow, use_case, current_user_id, status_filter, search_name, search_creator
):
    """Obtiene competiciones donde el usuario es creador O está inscrito."""
    async with uow:
        created_competitions = await _fetch_competitions_by_status(
            use_case,
            status_filter,
            str(current_user_id.value),
            search_name,
            search_creator,
        )

        enrollments = await uow.enrollments.find_by_user(current_user_id)

        enrollment_status_map = {
            enrollment.competition_id: enrollment.status for enrollment in enrollments
        }

        created_competition_ids = [c.id for c in created_competitions]

        enrolled_competitions = await _fetch_enrolled_competitions(
            uow,
            enrollments,
            created_competition_ids,
            status_filter,
            enrollment_status_map,
        )

        return created_competitions + enrolled_competitions


async def _map_competitions_to_dtos(competitions, current_user_id, uow, user_uow):
    result = []
    async with uow, user_uow:
        for competition in competitions:
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )
            result.append(dto)
    return result


async def _get_all_competitions(use_case, status_filter, creator_id, search_name, search_creator):
    """Obtiene todas las competiciones aplicando filtros (sin filtrar por usuario)."""
    return await _fetch_competitions_by_status(
        use_case, status_filter, creator_id, search_name, search_creator
    )


async def _exclude_user_competitions(competitions, current_user_id, uow):
    """Excluye competiciones donde el usuario es creador o está inscrito."""
    enrollments = await uow.enrollments.find_by_user(current_user_id)
    enrolled_competition_ids = {enrollment.competition_id for enrollment in enrollments}

    return [
        comp
        for comp in competitions
        if comp.creator_id != current_user_id and comp.id not in enrolled_competition_ids
    ]


# ======================================================================================
# CRUD ENDPOINTS
# ======================================================================================


@router.post(
    "",
    response_model=CreateCompetitionResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva competición",
    description="Crea una nueva competición en estado DRAFT. Requiere autenticación.",
    tags=["Competitions"],
)
@limiter.limit("10/hour")
async def create_competition(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    competition_data: CreateCompetitionRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CreateCompetitionUseCase = Depends(get_create_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Endpoint para crear una nueva competición."""
    try:
        creator_id = UserId(str(current_user.id))

        response = await use_case.execute(competition_data, creator_id)

        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(CompetitionId(response.id))

            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Competition created but not found",
                )

            enriched_dto = await CompetitionDTOMapper.to_response_dto(
                competition, creator_id, uow, user_uow
            )

            return CreateCompetitionResponseDTO(
                id=enriched_dto.id,
                creator_id=enriched_dto.creator_id,
                creator=enriched_dto.creator,
                name=enriched_dto.name,
                status=enriched_dto.status,
                start_date=enriched_dto.start_date,
                end_date=enriched_dto.end_date,
                country_code=enriched_dto.country_code,
                secondary_country_code=enriched_dto.secondary_country_code,
                tertiary_country_code=enriched_dto.tertiary_country_code,
                location=enriched_dto.location,
                countries=enriched_dto.countries,
                play_mode=enriched_dto.play_mode,
                max_players=enriched_dto.max_players,
                team_assignment=enriched_dto.team_assignment,
                team_1_name=competition.team_1_name,
                team_2_name=competition.team_2_name,
                is_creator=True,
                enrolled_count=0,
                created_at=enriched_dto.created_at,
                updated_at=enriched_dto.updated_at,
            )

    except CompetitionAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InvalidCountryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "",
    response_model=list[CompetitionResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar competiciones con filtros",
    description="Obtiene lista de competiciones con filtros opcionales.",
    tags=["Competitions"],
)
async def list_competitions(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListCompetitionsUseCase = Depends(get_list_competitions_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    status_filter: list[str] | None = Query(
        None,
        alias="status",
        description="Filtrar por estado (puede recibir múltiples valores)",
    ),
    creator_id: str | None = Query(None, description="Filtrar por creador (UUID)"),
    my_competitions: bool | None = Query(
        None,
        description="Si es True, devuelve competiciones del usuario. Si es False, las excluye.",
    ),
    search_name: str | None = Query(None, description="Buscar por nombre de competición"),
    search_creator: str | None = Query(None, description="Buscar por nombre del creador"),
):
    """Endpoint para listar competiciones con filtros opcionales."""
    try:
        current_user_id = UserId(str(current_user.id))
        sanitized_creator_id = _sanitize_creator_id(creator_id)

        if my_competitions is True:
            competitions = await _get_user_competitions(
                uow, use_case, current_user_id, status_filter, search_name, search_creator,
            )
        elif my_competitions is False:
            competitions = await _get_all_competitions(
                use_case, status_filter, sanitized_creator_id, search_name, search_creator,
            )
            async with uow:
                competitions = await _exclude_user_competitions(
                    competitions, current_user_id, uow
                )
        else:
            competitions = await _get_all_competitions(
                use_case, status_filter, sanitized_creator_id, search_name, search_creator,
            )

        result = await _map_competitions_to_dtos(competitions, current_user_id, uow, user_uow)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/{competition_id}",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener competición por ID",
    description="Obtiene el detalle completo de una competición.",
    tags=["Competitions"],
)
async def get_competition(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetCompetitionUseCase = Depends(get_get_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Endpoint para obtener el detalle de una competición."""
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        competition = await use_case.execute(competition_vo_id)

        async with uow, user_uow:
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except GetNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put(
    "/{competition_id}",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar competición",
    description="Actualiza una competición (SOLO en estado DRAFT y SOLO el creador).",
    tags=["Competitions"],
)
async def update_competition(
    competition_id: UUID,
    request: UpdateCompetitionRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: UpdateCompetitionUseCase = Depends(get_update_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Endpoint para actualizar una competición."""
    try:
        current_user_id = UserId(str(current_user.id))
        competition_vo_id = CompetitionId(competition_id)

        await use_case.execute(competition_vo_id, request, current_user_id)

        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except UpdateNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except UpdateNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionNotEditableError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete(
    "/{competition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar competición",
    description="Elimina físicamente una competición (SOLO en estado DRAFT y SOLO el creador).",
    tags=["Competitions"],
)
async def delete_competition(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: DeleteCompetitionUseCase = Depends(get_delete_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),  # noqa: ARG001
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),  # noqa: ARG001
):
    """Endpoint para eliminar físicamente una competición."""
    try:
        current_user_id = UserId(str(current_user.id))

        request_dto = DeleteCompetitionRequestDTO(competition_id=competition_id)

        await use_case.execute(request_dto, current_user_id)

        return

    except DeleteNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DeleteNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionNotDeletableError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
