"""
Endpoints del mapa de hoyos de un recorrido (BE #532).

- GET  /golf-courses/{id}/hole-map                       mapa aprobado (cualquier usuario)
- GET  /golf-courses/admin/hole-maps/pending             pendientes de revisión (admin)
- GET  /golf-courses/admin/{id}/hole-map                 mapa en cualquier estado (admin)
- PUT  /golf-courses/admin/{id}/hole-map/approve|reject  revisar la versión vista (admin)
- PUT  /golf-courses/{id}/hole-map/marks/{hole}          marcar un hoyo (cualquier usuario)
- GET  /golf-courses/{id}/hole-map/marks/mine            mis marcas en el campo

Los errores llevan un mensaje fijo y un `error_code` del que se fía el front:
nunca el texto de una excepción (CodeQL, BE #562).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from src.config.dependencies import (
    get_approve_hole_map_use_case,
    get_approved_hole_map_use_case,
    get_current_user,
    get_hole_map_for_review_use_case,
    get_list_my_hole_marks_use_case,
    get_list_pending_hole_maps_use_case,
    get_reject_hole_map_use_case,
    get_save_hole_mark_use_case,
)
from src.config.rate_limit import limiter
from src.modules.golf_course.application.dtos.hole_map_dtos import (
    ApproveHoleMapBodyDTO,
    GetHoleMapRequestDTO,
    HoleMapDTO,
    HoleMapReviewDTO,
    ListPendingHoleMapsRequestDTO,
    PendingHoleMapDTO,
    RejectHoleMapBodyDTO,
    ReviewHoleMapRequestDTO,
)
from src.modules.golf_course.application.dtos.hole_mark_dtos import (
    HoleMarkBodyDTO,
    HoleMarkDTO,
    ListMyHoleMarksRequestDTO,
    SaveHoleMarkRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleAlreadyMappedError,
    HoleMapChangedError,
    HoleMapNotFoundError,
    HoleNotInCourseError,
    TeeRequiredError,
)
from src.modules.golf_course.application.use_cases.hole_map_use_cases import (
    ApproveHoleMapUseCase,
    GetApprovedHoleMapUseCase,
    GetHoleMapForReviewUseCase,
    ListPendingHoleMapsUseCase,
    RejectHoleMapUseCase,
)
from src.modules.golf_course.application.use_cases.hole_mark_use_cases import (
    ListMyHoleMarksUseCase,
    SaveHoleMarkUseCase,
)
from src.modules.golf_course.domain.entities.course_hole_map import (
    HoleMapNotPendingError,
    RejectionReasonTooLongError,
)
from src.modules.golf_course.domain.entities.hole_mark import (
    HoleMarkFarFromCourseError,
    HoleMarkOutOfRangeError,
    InvalidHoleMarkError,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO

router = APIRouter(prefix="/golf-courses")


def _error(status_code: int, error_code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"detail": detail, "error_code": error_code}
    )


def _not_found() -> JSONResponse:
    return _error(status.HTTP_404_NOT_FOUND, "HOLE_MAP_NOT_FOUND", "This course has no hole map")


def _forbidden() -> JSONResponse:
    return _error(status.HTTP_403_FORBIDDEN, "ADMIN_REQUIRED", "Only admins can review hole maps")


@router.get(
    "/{golf_course_id}/hole-map",
    response_model=HoleMapDTO,
    responses={404: {"description": "HOLE_MAP_NOT_FOUND"}},
)
async def get_hole_map(
    golf_course_id: UUID,
    current_user: Annotated[  # noqa: ARG001 - Solo exige sesión: el mapa es para cualquiera
        UserResponseDTO, Depends(get_current_user)
    ],
    use_case: Annotated[GetApprovedHoleMapUseCase, Depends(get_approved_hole_map_use_case)],
):
    """El mapa APROBADO del campo, en GeoJSON. Sin mapa aprobado: 404 HOLE_MAP_NOT_FOUND."""
    try:
        return await use_case.execute(GetHoleMapRequestDTO(golf_course_id=str(golf_course_id)))
    except HoleMapNotFoundError:
        return _not_found()


@router.get(
    "/admin/hole-maps/pending",
    response_model=list[PendingHoleMapDTO],
    tags=["admin"],
    responses={403: {"description": "ADMIN_REQUIRED"}},
)
async def list_pending_hole_maps(
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[ListPendingHoleMapsUseCase, Depends(get_list_pending_hole_maps_use_case)],
):
    """Los mapas pendientes de revisión, del más antiguo al más reciente."""
    if not current_user.is_admin:
        return _forbidden()
    return await use_case.execute(ListPendingHoleMapsRequestDTO())


@router.get(
    "/admin/{golf_course_id}/hole-map",
    response_model=HoleMapReviewDTO,
    tags=["admin"],
    responses={403: {"description": "ADMIN_REQUIRED"}, 404: {"description": "HOLE_MAP_NOT_FOUND"}},
)
async def get_hole_map_for_review(
    golf_course_id: UUID,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[GetHoleMapForReviewUseCase, Depends(get_hole_map_for_review_use_case)],
):
    """El mapa del campo en cualquier estado, para revisarlo."""
    if not current_user.is_admin:
        return _forbidden()
    try:
        return await use_case.execute(GetHoleMapRequestDTO(golf_course_id=str(golf_course_id)))
    except HoleMapNotFoundError:
        return _not_found()


async def _review(
    use_case: ApproveHoleMapUseCase | RejectHoleMapUseCase,
    golf_course_id: UUID,
    current_user: UserResponseDTO,
    body: ApproveHoleMapBodyDTO,
):
    if not current_user.is_admin:
        return _forbidden()
    try:
        return await use_case.execute(
            ReviewHoleMapRequestDTO(
                golf_course_id=str(golf_course_id),
                reviewer_id=str(current_user.id),
                version=body.version,
                reason=getattr(body, "reason", None),
            )
        )
    except HoleMapNotFoundError:
        return _not_found()
    except HoleMapChangedError:
        return _error(
            status.HTTP_409_CONFLICT,
            "HOLE_MAP_CHANGED",
            "The hole map changed while it was being reviewed; review it again",
        )
    except HoleMapNotPendingError:
        return _error(
            status.HTTP_409_CONFLICT, "HOLE_MAP_NOT_PENDING", "The hole map is already reviewed"
        )
    except RejectionReasonTooLongError:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_REJECTION_REASON",
            "The rejection reason must be at most 500 characters",
        )


REVIEW_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"description": "ADMIN_REQUIRED"},
    404: {"description": "HOLE_MAP_NOT_FOUND"},
    409: {"description": "HOLE_MAP_CHANGED or HOLE_MAP_NOT_PENDING"},
}


@router.put(
    "/admin/{golf_course_id}/hole-map/approve",
    response_model=HoleMapReviewDTO,
    tags=["admin"],
    responses=REVIEW_RESPONSES,
)
async def approve_hole_map(
    golf_course_id: UUID,
    body: ApproveHoleMapBodyDTO,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[ApproveHoleMapUseCase, Depends(get_approve_hole_map_use_case)],
):
    """Aprueba la versión vista (`version`); si cambió, 409 HOLE_MAP_CHANGED."""
    return await _review(use_case, golf_course_id, current_user, body)


@router.put(
    "/admin/{golf_course_id}/hole-map/reject",
    response_model=HoleMapReviewDTO,
    tags=["admin"],
    responses={**REVIEW_RESPONSES, 400: {"description": "INVALID_REJECTION_REASON"}},
)
async def reject_hole_map(
    golf_course_id: UUID,
    body: RejectHoleMapBodyDTO,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[RejectHoleMapUseCase, Depends(get_reject_hole_map_use_case)],
):
    """Rechaza la versión vista, con un motivo opcional (500 caracteres como mucho)."""
    return await _review(use_case, golf_course_id, current_user, body)


# ============================================================================
# Marcas de hoyo de los jugadores (PR C)
# ============================================================================


def _course_not_found() -> JSONResponse:
    return _error(status.HTTP_404_NOT_FOUND, "GOLF_COURSE_NOT_FOUND", "Golf course not found")


MARK_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"description": "GOLF_COURSE_NOT_FOUND"},
    409: {"description": "HOLE_ALREADY_MAPPED"},
    422: {
        "description": (
            "HOLE_NOT_IN_COURSE, TEE_REQUIRED, INVALID_HOLE_MARK, HOLE_MARK_OUT_OF_RANGE "
            "or HOLE_MARK_TOO_FAR_FROM_COURSE"
        )
    },
}

_MARK_ERRORS: dict[type[Exception], tuple[int, str, str]] = {
    HoleNotInCourseError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "HOLE_NOT_IN_COURSE",
        "This course has no such hole",
    ),
    HoleAlreadyMappedError: (
        status.HTTP_409_CONFLICT,
        "HOLE_ALREADY_MAPPED",
        "This hole already has its tee and green",
    ),
    TeeRequiredError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "TEE_REQUIRED",
        "This hole has no tee: mark the tee too",
    ),
    HoleMarkOutOfRangeError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "HOLE_MARK_OUT_OF_RANGE",
        "The green must be 40-750 m from the tee",
    ),
    HoleMarkFarFromCourseError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "HOLE_MARK_TOO_FAR_FROM_COURSE",
        "Every point must be within 3 km of the course",
    ),
    InvalidHoleMarkError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "INVALID_HOLE_MARK",
        "The hole mark is not valid",
    ),
}


@router.put(
    "/{golf_course_id}/hole-map/marks/{hole_number}",
    response_model=HoleMarkDTO,
    responses=MARK_RESPONSES,
)
@limiter.limit("60/minute")  # Por usuario: una vuelta son 18, y la cola los manda seguidos
async def save_hole_mark(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    golf_course_id: UUID,
    hole_number: int,
    body: HoleMarkBodyDTO,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[SaveHoleMarkUseCase, Depends(get_save_hole_mark_use_case)],
):
    """
    Marca un hoyo (o lo vuelve a marcar: sustituye tu marca, salvo que la tuya
    guardada sea más nueva que `marked_at`). Sin salida en el mapa: salida, hasta
    dos codos y centro del green; con salida, solo cuenta el green. Devuelve la
    marca que queda guardada.
    """
    try:
        return await use_case.execute(
            SaveHoleMarkRequestDTO(
                golf_course_id=str(golf_course_id),
                hole_number=hole_number,
                user_id=str(current_user.id),
                tee=body.tee,
                bends=body.bends,
                green_center=body.green_center,
                marked_at=body.marked_at,
            )
        )
    except GolfCourseNotFoundError:
        return _course_not_found()
    except tuple(_MARK_ERRORS) as e:
        return _error(*_MARK_ERRORS[type(e)])


@router.get(
    "/{golf_course_id}/hole-map/marks/mine",
    response_model=list[HoleMarkDTO],
    responses={404: {"description": "GOLF_COURSE_NOT_FOUND"}},
)
async def list_my_hole_marks(
    golf_course_id: UUID,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[ListMyHoleMarksUseCase, Depends(get_list_my_hole_marks_use_case)],
):
    """Tus marcas en el campo, por orden de hoyo."""
    try:
        return await use_case.execute(
            ListMyHoleMarksRequestDTO(
                golf_course_id=str(golf_course_id), user_id=str(current_user.id)
            )
        )
    except GolfCourseNotFoundError:
        return _course_not_found()
