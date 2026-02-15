"""Competition Golf Course Management Routes - add, remove, reorder, list."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.config.dependencies import (
    get_add_golf_course_to_competition_use_case,
    get_competition_uow,
    get_current_user,
    get_remove_golf_course_from_competition_use_case,
    get_reorder_golf_courses_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.competition_dto import (
    AddGolfCourseBodyDTO,
    AddGolfCourseRequestDTO,
    AddGolfCourseResponseDTO,
    CompetitionGolfCourseResponseDTO,
    GolfCourseDetailDTO,
    HoleResponseDTO,
    RemoveGolfCourseRequestDTO,
    RemoveGolfCourseResponseDTO,
    ReorderGolfCourseIdsRequest,
    ReorderGolfCoursesRequestDTO,
    ReorderGolfCoursesResponseDTO,
    TeeResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.add_golf_course_use_case import (
    AddGolfCourseToCompetitionUseCase,
    CompetitionNotDraftError as AddGCNotDraftError,
    CompetitionNotFoundError as AddGCNotFoundError,
    GolfCourseAlreadyAssignedError,
    GolfCourseNotApprovedError,
    GolfCourseNotFoundError,
    IncompatibleCountryError,
    NotCompetitionCreatorError as AddGCNotCreatorError,
)
from src.modules.competition.application.use_cases.remove_golf_course_use_case import (
    CompetitionNotDraftError as RemoveGCNotDraftError,
    GolfCourseNotAssignedError,
    RemoveGolfCourseFromCompetitionUseCase,
)
from src.modules.competition.application.use_cases.reorder_golf_courses_use_case import (
    CompetitionNotDraftError as ReorderNotDraftError,
    CompetitionNotFoundError as ReorderNotFoundError,
    InvalidReorderError,
    NotCompetitionCreatorError as ReorderNotCreatorError,
    ReorderGolfCoursesUseCase,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

# Aliases for shared exceptions
RemoveGCNotFoundError = CompetitionNotFoundError
RemoveGCNotCreatorError = NotCompetitionCreatorError

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================================================================================
# GOLF COURSE MANAGEMENT ENDPOINTS
# ======================================================================================


@router.post(
    "/{competition_id}/golf-courses",
    response_model=AddGolfCourseResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir campo de golf a competición",
    tags=["Competitions - Golf Courses"],
)
@limiter.limit("10/minute")
async def add_golf_course_to_competition(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    golf_course_body: AddGolfCourseBodyDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: AddGolfCourseToCompetitionUseCase = Depends(
        get_add_golf_course_to_competition_use_case
    ),
):
    """Añade un campo de golf aprobado a una competición en estado DRAFT."""
    try:
        current_user_id = UserId(current_user.id)

        request_dto = AddGolfCourseRequestDTO(
            competition_id=competition_id,
            golf_course_id=golf_course_body.golf_course_id,
        )

        response = await use_case.execute(request_dto, current_user_id)

        return response

    except AddGCNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GolfCourseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except AddGCNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (
        AddGCNotDraftError,
        GolfCourseNotApprovedError,
        GolfCourseAlreadyAssignedError,
        IncompatibleCountryError,
    ) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete(
    "/{competition_id}/golf-courses/{golf_course_id}",
    response_model=RemoveGolfCourseResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Eliminar campo de golf de competición",
    tags=["Competitions - Golf Courses"],
)
@limiter.limit("10/minute")
async def remove_golf_course_from_competition(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    golf_course_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: RemoveGolfCourseFromCompetitionUseCase = Depends(
        get_remove_golf_course_from_competition_use_case
    ),
):
    """Elimina un campo de golf de una competición en estado DRAFT."""
    try:
        current_user_id = UserId(current_user.id)

        request_dto = RemoveGolfCourseRequestDTO(
            competition_id=competition_id,
            golf_course_id=golf_course_id,
        )

        response = await use_case.execute(request_dto, current_user_id)

        return response

    except RemoveGCNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RemoveGCNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (RemoveGCNotDraftError, GolfCourseNotAssignedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put(
    "/{competition_id}/golf-courses/reorder",
    response_model=ReorderGolfCoursesResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Reordenar campos de golf en competición",
    tags=["Competitions - Golf Courses"],
)
@limiter.limit("10/minute")
async def reorder_golf_courses(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    reorder_body: ReorderGolfCourseIdsRequest,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ReorderGolfCoursesUseCase = Depends(get_reorder_golf_courses_use_case),
):
    """Reordena los campos de golf asociados a una competición en estado DRAFT."""
    try:
        current_user_id = UserId(current_user.id)

        request_dto = ReorderGolfCoursesRequestDTO(
            competition_id=competition_id,
            golf_course_ids=reorder_body.golf_course_ids,
        )

        response = await use_case.execute(request_dto, current_user_id)

        return response

    except ReorderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ReorderNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (ReorderNotDraftError, InvalidReorderError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/{competition_id}/golf-courses",
    response_model=list[CompetitionGolfCourseResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar campos de golf de una competición",
    tags=["Competitions - Golf Courses"],
)
@limiter.limit("20/minute")
async def list_competition_golf_courses(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
):
    """Obtiene la lista ordenada de campos de golf asociados a una competición."""
    try:
        competition_vo_id = CompetitionId(competition_id)

        async with uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)

            if not competition:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No existe competición con ID {competition_id}",
                )

            golf_courses_list = []
            for gc in competition.golf_courses:
                if gc.golf_course is None:
                    logger.error(
                        f"golf_course is None for CompetitionGolfCourse {gc.id}, "
                        f"golf_course_id={gc.golf_course_id.value}"
                    )
                    continue

                golf_course = gc.golf_course
                golf_courses_list.append(
                    CompetitionGolfCourseResponseDTO(
                        golf_course_id=gc.golf_course_id.value,
                        display_order=gc.display_order,
                        created_at=gc.created_at,
                        golf_course=GolfCourseDetailDTO(
                            id=golf_course.id.value,
                            name=golf_course.name,
                            country_code=golf_course.country_code.value,
                            course_type=golf_course.course_type.value,
                            total_par=golf_course.total_par,
                            approval_status=golf_course.approval_status.value,
                            tees=[
                                TeeResponseDTO(
                                    category=tee.category.value,
                                    gender=tee.gender.value if tee.gender else None,
                                    identifier=tee.identifier,
                                    course_rating=float(tee.course_rating),
                                    slope_rating=int(tee.slope_rating),
                                )
                                for tee in (golf_course.tees or [])
                            ],
                            holes=[
                                HoleResponseDTO(
                                    hole_number=hole.number,
                                    par=hole.par,
                                    stroke_index=hole.stroke_index,
                                )
                                for hole in (golf_course.holes or [])
                            ],
                        ),
                    )
                )

            return golf_courses_list

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error loading golf courses for competition {competition_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al cargar campos de golf: {type(e).__name__}",
        ) from e
