"""
Endpoints del mapa de hoyos de un recorrido (BE #532).

- GET  /golf-courses/{id}/hole-map                       mapa aprobado (cualquier usuario)
- GET  /golf-courses/admin/hole-maps/pending             pendientes de revisión (admin)
- GET  /golf-courses/admin/{id}/hole-map                 mapa en cualquier estado (admin)
- PUT  /golf-courses/admin/{id}/hole-map/approve|reject  revisar la versión vista (admin)
- POST /golf-courses/{id}/hole-map/samples/{hole}        mandar una muestra anónima de un hoyo
- GET  /golf-courses/{id}/hole-map/samples               primera muestra de cada hoyo

Los errores llevan un mensaje fijo y un `error_code` del que se fía el front:
nunca el texto de una excepción (CodeQL, BE #562).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, Response

from src.config.dependencies import (
    get_approve_hole_map_use_case,
    get_approved_hole_map_use_case,
    get_current_user,
    get_hole_map_for_review_use_case,
    get_list_hole_samples_use_case,
    get_list_pending_hole_maps_use_case,
    get_reject_hole_map_use_case,
    get_submit_hole_sample_use_case,
)
from src.config.rate_limit import get_hole_sample_rate_limit_key, limiter
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
from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    HoleSampleBodyDTO,
    HoleSampleStatusDTO,
    ListHoleSamplesRequestDTO,
    SubmitHoleSampleRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleMapChangedError,
    HoleMapNotFoundError,
    HoleNotInCourseError,
)
from src.modules.golf_course.application.use_cases.hole_map_use_cases import (
    ApproveHoleMapUseCase,
    GetApprovedHoleMapUseCase,
    GetHoleMapForReviewUseCase,
    ListPendingHoleMapsUseCase,
    RejectHoleMapUseCase,
)
from src.modules.golf_course.application.use_cases.hole_sample_use_cases import (
    ListHoleSamplesUseCase,
    SubmitHoleSampleUseCase,
)
from src.modules.golf_course.domain.entities.course_hole_map import (
    HoleMapNotPendingError,
    RejectionReasonTooLongError,
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
# Muestras anónimas de hoyo (16 oct 2026)
# ============================================================================


def _course_not_found() -> JSONResponse:
    return _error(status.HTTP_404_NOT_FOUND, "GOLF_COURSE_NOT_FOUND", "Golf course not found")


@router.post(
    "/{golf_course_id}/hole-map/samples/{hole_number}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        404: {"description": "GOLF_COURSE_NOT_FOUND"},
        422: {"description": "HOLE_NOT_IN_COURSE, or a malformed body"},
    },
)
# Por usuario (una vuelta son 18, y la cola los manda seguidos), con una clave que
# en el log no dice quién
@limiter.limit("60/minute", key_func=get_hole_sample_rate_limit_key)
async def submit_hole_sample(
    request: Request,  # noqa: ARG001 - Requerido por SlowAPI limiter
    golf_course_id: UUID,
    hole_number: int,
    body: HoleSampleBodyDTO,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[SubmitHoleSampleUseCase, Depends(get_submit_hole_sample_use_case)],
):
    """
    Manda una muestra de un hoyo desde una barra: su id (lo genera el móvil), el
    color y el género de la barra, la salida, hasta dos codos y el centro del
    green; sin salida ni codos, una muestra solo green. Responde 204 tanto si se
    guarda como si no (el hoyo ya tiene sus tres, o ya tiene su solo green; el
    mapa de OSM aprobado ya lo trae con línea y green; el id ya llegó; ya
    mandaste otra a ese hoyo hace menos de 10 minutos; o la muestra no vale). Con
    la muestra no se guarda quién la manda; Sentry tampoco recibe al usuario en
    esta ruta.
    """
    try:
        await use_case.execute(
            SubmitHoleSampleRequestDTO(
                id=body.id,
                golf_course_id=str(golf_course_id),
                hole_number=hole_number,
                user_id=str(current_user.id),
                tee_color=body.tee_color,
                tee_gender=body.tee_gender,
                tee=body.tee,
                bends=body.bends,
                green_center=body.green_center,
            )
        )
    except GolfCourseNotFoundError:
        return _course_not_found()
    except HoleNotInCourseError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "HOLE_NOT_IN_COURSE",
            "This course has no such hole",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{golf_course_id}/hole-map/samples",
    response_model=list[HoleSampleStatusDTO],
    responses={404: {"description": "GOLF_COURSE_NOT_FOUND"}},
)
async def list_hole_samples(
    golf_course_id: UUID,
    current_user: Annotated[  # noqa: ARG001 - Solo exige sesión
        UserResponseDTO, Depends(get_current_user)
    ],
    use_case: Annotated[ListHoleSamplesUseCase, Depends(get_list_hole_samples_use_case)],
):
    """
    Los 18 hoyos; de cada uno, su primera muestra completa, el green de su
    muestra solo green y si sigue recogiendo. `tees` (por barra) queda para los
    móviles de antes del 17 oct.
    """
    try:
        response = await use_case.execute(
            ListHoleSamplesRequestDTO(golf_course_id=str(golf_course_id))
        )
    except GolfCourseNotFoundError:
        return _course_not_found()
    return response.holes
