"""
Endpoints del mapa de hoyos de un recorrido (BE #532).

- GET  /golf-courses/{id}/hole-map                       mapa aprobado (cualquier usuario)
- GET  /golf-courses/admin/hole-maps/pending             pendientes de revisión (admin)
- GET  /golf-courses/admin/{id}/hole-map                 mapa en cualquier estado (admin)
- PUT  /golf-courses/admin/{id}/hole-map/approve|reject  revisar la versión vista (admin)

Los errores llevan un mensaje fijo y un `error_code` del que se fía el front:
nunca el texto de una excepción (CodeQL, BE #562).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from src.config.dependencies import (
    get_approve_hole_map_use_case,
    get_approved_hole_map_use_case,
    get_current_user,
    get_hole_map_for_review_use_case,
    get_list_pending_hole_maps_use_case,
    get_reject_hole_map_use_case,
)
from src.modules.golf_course.application.dtos.hole_map_dtos import (
    HoleMapDTO,
    HoleMapReviewDTO,
    PendingHoleMapDTO,
    ReviewHoleMapRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    HoleMapChangedError,
    HoleMapNotFoundError,
    HoleMapNotPendingError,
)
from src.modules.golf_course.application.use_cases.hole_map_use_cases import (
    ApproveHoleMapUseCase,
    GetApprovedHoleMapUseCase,
    GetHoleMapForReviewUseCase,
    ListPendingHoleMapsUseCase,
    RejectHoleMapUseCase,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId

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
        return await use_case.execute(str(golf_course_id))
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
    return await use_case.execute()


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
        return await use_case.execute(str(golf_course_id))
    except HoleMapNotFoundError:
        return _not_found()


async def _review(
    use_case: ApproveHoleMapUseCase | RejectHoleMapUseCase,
    golf_course_id: UUID,
    current_user: UserResponseDTO,
    request: ReviewHoleMapRequestDTO,
):
    if not current_user.is_admin:
        return _forbidden()
    try:
        return await use_case.execute(str(golf_course_id), UserId(str(current_user.id)), request)
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
    except ValueError:
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
    request: ReviewHoleMapRequestDTO,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[ApproveHoleMapUseCase, Depends(get_approve_hole_map_use_case)],
):
    """Aprueba la versión vista (`version`); si cambió, 409 HOLE_MAP_CHANGED."""
    return await _review(use_case, golf_course_id, current_user, request)


@router.put(
    "/admin/{golf_course_id}/hole-map/reject",
    response_model=HoleMapReviewDTO,
    tags=["admin"],
    responses={**REVIEW_RESPONSES, 400: {"description": "INVALID_REJECTION_REASON"}},
)
async def reject_hole_map(
    golf_course_id: UUID,
    request: ReviewHoleMapRequestDTO,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[RejectHoleMapUseCase, Depends(get_reject_hole_map_use_case)],
):
    """Rechaza la versión vista, con un motivo opcional (500 caracteres como mucho)."""
    return await _review(use_case, golf_course_id, current_user, request)
