"""Competition Golf Course Management Routes - add, remove, reorder, list."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.config.dependencies import (
    get_add_golf_course_to_competition_use_case,
    get_competition_course_tees_use_case,
    get_competition_uow,
    get_current_user,
    get_remove_golf_course_from_competition_use_case,
    get_reorder_golf_courses_use_case,
    get_set_competition_course_tee_use_case,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.competition_dto import (
    AddGolfCourseBodyDTO,
    AddGolfCourseRequestDTO,
    AddGolfCourseResponseDTO,
    CompetitionCourseTeeResponseDTO,
    CompetitionGolfCourseResponseDTO,
    CourseTeeForGenderDTO,
    GetCompetitionCourseTeesRequestDTO,
    GolfCourseDetailDTO,
    HoleResponseDTO,
    RemoveGolfCourseRequestDTO,
    RemoveGolfCourseResponseDTO,
    ReorderGolfCourseIdsRequest,
    ReorderGolfCoursesRequestDTO,
    ReorderGolfCoursesResponseDTO,
    SetCompetitionCourseTeeRequestDTO,
    TeeResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.add_golf_course_use_case import (
    AddGolfCourseToCompetitionUseCase,
    GolfCourseAlreadyAssignedError,
    GolfCourseNotApprovedError,
    IncompatibleCountryError,
)
from src.modules.competition.application.use_cases.get_competition_course_tees_use_case import (
    GetCompetitionCourseTeesUseCase,
)
from src.modules.competition.application.use_cases.remove_golf_course_use_case import (
    RemoveGolfCourseFromCompetitionUseCase,
)
from src.modules.competition.application.use_cases.reorder_golf_courses_use_case import (
    ReorderGolfCoursesUseCase,
)
from src.modules.competition.application.use_cases.set_competition_course_tee_use_case import (
    SetCompetitionCourseTeeUseCase,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.api.v1.errores_de_barras import (
    ERRORES_DE_BARRAS,
    respuesta_de_barras,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender

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
    """Añade un campo de golf aprobado a una competición no terminada ni cancelada."""
    try:
        current_user_id = UserId(current_user.id)

        request_dto = AddGolfCourseRequestDTO(
            competition_id=competition_id,
            golf_course_id=golf_course_body.golf_course_id,
        )

        response = await use_case.execute(
            request_dto, current_user_id, is_admin=current_user.is_admin
        )

        return response

    except (
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
    current_user_id = UserId(current_user.id)

    request_dto = RemoveGolfCourseRequestDTO(
        competition_id=competition_id,
        golf_course_id=golf_course_id,
    )

    response = await use_case.execute(request_dto, current_user_id, is_admin=current_user.is_admin)

    return response


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
    current_user_id = UserId(current_user.id)

    request_dto = ReorderGolfCoursesRequestDTO(
        competition_id=competition_id,
        golf_course_ids=reorder_body.golf_course_ids,
    )

    response = await use_case.execute(request_dto, current_user_id, is_admin=current_user.is_admin)

    return response


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
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001 - Auth required
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
                # La relación la añade el mapeo imperativo (persistence/sqlalchemy/mappers.py),
                # no la entidad, y el repositorio la carga con selectinload
                golf_course: GolfCourse | None = gc.golf_course  # type: ignore[attr-defined]
                if golf_course is None:
                    logger.error(
                        f"golf_course is None for CompetitionGolfCourse {gc.id}, "
                        f"golf_course_id={gc.golf_course_id.value}"
                    )
                    continue

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
                            timezone=golf_course.timezone,
                            tees=[
                                TeeResponseDTO(
                                    color=tee.color.value,
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
                                for hole in (golf_course.reference_card or [])
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
            detail="Error interno al cargar campos de golf",
        ) from e


class SetCourseTeeBody(BaseModel):
    """La barra del campo para un género; null la quita (barras por campo)."""

    gender: Gender = Field(..., description="MALE o FEMALE.")
    tee_color: TeeColor | None = Field(
        ..., description="Las barras de ese campo para ese género, o null para quitarlas."
    )


@router.put(
    "/{competition_id}/courses/{golf_course_id}/tee",
    response_model=CompetitionCourseTeeResponseDTO,
    summary="Fijar la barra de un campo para todos los de un género",
    description=(
        "Solo el organizador o un admin, también con la competición en curso. Pisa la "
        "barra general de los de ese género, no el cambio propio de nadie, y rehace lo "
        "que les queda por jugar en ese campo: todo o nada. 422 TEE_NOT_AVAILABLE si "
        "es OTHER, si ese campo no tiene esa barra para ese género, o si al quitarla (null) a alguno "
        "con algo por jugar allí no le valdría la que quedaría (texto propio)."
    ),
    tags=["Competitions - Golf Courses"],
)
async def set_competition_course_tee(
    competition_id: UUID,
    golf_course_id: UUID,
    body: SetCourseTeeBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SetCompetitionCourseTeeUseCase = Depends(get_set_competition_course_tee_use_case),
):
    """La barra de un campo para todos los de un género (barras por campo, 20 nov 2026)."""
    try:
        return await use_case.execute(
            SetCompetitionCourseTeeRequestDTO(
                competition_id=competition_id,
                golf_course_id=golf_course_id,
                gender=body.gender,
                tee_color=body.tee_color,
            ),
            UserId(str(current_user.id)),
            is_admin=current_user.is_admin,
        )
    except ERRORES_DE_BARRAS as e:
        return respuesta_de_barras(e)


@router.get(
    "/{competition_id}/course-tees",
    response_model=list[CourseTeeForGenderDTO],
    summary="La barra fijada en cada campo para cada género",
    description=(
        "Lo que el organizador fijó en cada campo de la competición para todos los de un "
        "género, en el orden de los campos; vacío si no hay nada. Solo el organizador o un "
        "admin (403 a los demás), en cualquier estado de la competición."
    ),
    tags=["Competitions - Golf Courses"],
)
async def get_competition_course_tees(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetCompetitionCourseTeesUseCase = Depends(get_competition_course_tees_use_case),
):
    """Lo fijado por campo y género (barras por campo, tabla del 21 nov 2026, A)."""
    return await use_case.execute(
        GetCompetitionCourseTeesRequestDTO(competition_id=competition_id),
        UserId(str(current_user.id)),
        is_admin=current_user.is_admin,
    )
