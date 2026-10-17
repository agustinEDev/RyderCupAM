"""
Endpoints del mapa de hoyos de un recorrido (BE #532).

- GET  /golf-courses/{id}/hole-map                       mapa aprobado (cualquier usuario)
- GET  /golf-courses/admin/hole-maps/pending             pendientes de revisión (admin)
- GET  /golf-courses/admin/{id}/hole-map                 mapa en cualquier estado (admin)
- PUT  /golf-courses/admin/{id}/hole-map/approve|reject  revisar la versión vista (admin)
- POST /golf-courses/{id}/hole-map/samples/{hole}        mandar una muestra anónima de un hoyo
- GET  /golf-courses/{id}/hole-map/samples               primera muestra de cada hoyo
- PUT  /golf-courses/admin/{id}/hole-lines/{hole}        guardar la línea del hoyo (admin)
- DELETE /golf-courses/admin/{id}/hole-lines/{hole}      reabrir el hoyo (admin)
- DELETE /golf-courses/admin/{id}/hole-samples/{sample}  borrar una muestra mala (admin)
- GET  /golf-courses/admin/hole-reviews                  campos con hoyos por revisar (admin)
- GET  /golf-courses/admin/{id}/hole-reviews             los 18 hoyos de un campo para revisar (admin)

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
    get_delete_hole_sample_use_case,
    get_hole_map_for_review_use_case,
    get_hole_review_use_case,
    get_list_hole_reviews_use_case,
    get_list_hole_samples_use_case,
    get_list_pending_hole_maps_use_case,
    get_reject_hole_map_use_case,
    get_reopen_hole_use_case,
    get_save_hole_line_use_case,
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
from src.modules.golf_course.application.dtos.hole_review_dtos import (
    GetHoleReviewRequestDTO,
    HoleReviewDTO,
    ListHoleReviewsRequestDTO,
    ListHoleReviewsResponseDTO,
)
from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    HoleSampleBodyDTO,
    HoleSampleDTO,
    HoleSampleStatusDTO,
    ListHoleSamplesRequestDTO,
    SubmitHoleSampleRequestDTO,
)
from src.modules.golf_course.application.dtos.saved_hole_dtos import (
    DeleteHoleSampleRequestDTO,
    ReopenHoleRequestDTO,
    SaveHoleLineBodyDTO,
    SaveHoleLineRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleMapChangedError,
    HoleMapNotFoundError,
    HoleNotInCourseError,
    HoleSampleNotFoundError,
    InvalidHoleLineError,
)
from src.modules.golf_course.application.use_cases.hole_map_use_cases import (
    ApproveHoleMapUseCase,
    GetApprovedHoleMapUseCase,
    GetHoleMapForReviewUseCase,
    ListPendingHoleMapsUseCase,
    RejectHoleMapUseCase,
)
from src.modules.golf_course.application.use_cases.hole_review_use_cases import (
    GetHoleReviewUseCase,
    ListHoleReviewsUseCase,
)
from src.modules.golf_course.application.use_cases.hole_sample_use_cases import (
    ListHoleSamplesUseCase,
    SubmitHoleSampleUseCase,
)
from src.modules.golf_course.application.use_cases.saved_hole_use_cases import (
    DeleteHoleSampleUseCase,
    ReopenHoleUseCase,
    SaveHoleLineUseCase,
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


# ============================================================================
# La línea de cada hoyo, que guarda el admin (BE #575, 17 oct 2026)
# ============================================================================

_HOLE_NOT_IN_COURSE = (
    status.HTTP_422_UNPROCESSABLE_CONTENT,
    "HOLE_NOT_IN_COURSE",
    "This course has no such hole",
)


@router.put(
    "/admin/{golf_course_id}/hole-lines/{hole_number}",
    response_model=HoleSampleDTO,
    tags=["admin"],
    responses={
        403: {"description": "ADMIN_REQUIRED"},
        404: {"description": "GOLF_COURSE_NOT_FOUND"},
        422: {"description": "HOLE_NOT_IN_COURSE or INVALID_HOLE_LINE"},
    },
)
async def save_hole_line(
    golf_course_id: UUID,
    hole_number: int,
    body: SaveHoleLineBodyDTO,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[SaveHoleLineUseCase, Depends(get_save_hole_line_use_case)],
):
    """
    Guarda la línea de referencia del hoyo (la salida, hasta dos codos y el centro
    del green), o la sustituye si ya había una. La ven todos los jugadores, y el
    hoyo deja de recoger muestras. 422 INVALID_HOLE_LINE si no vale (codos de
    más, el green a menos de 40 o más de 750 m de la salida, un punto a más de 3
    km del campo).
    """
    if not current_user.is_admin:
        return _forbidden()
    try:
        return await use_case.execute(
            SaveHoleLineRequestDTO(
                golf_course_id=str(golf_course_id),
                hole_number=hole_number,
                admin_id=str(current_user.id),
                tee=body.tee,
                bends=body.bends,
                green_center=body.green_center,
            )
        )
    except GolfCourseNotFoundError:
        return _course_not_found()
    except HoleNotInCourseError:
        return _error(*_HOLE_NOT_IN_COURSE)
    except InvalidHoleLineError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_HOLE_LINE",
            "The line needs at most two bends, the green 40-750 m from the tee, "
            "and every point within 3 km of the course",
        )


@router.delete(
    "/admin/{golf_course_id}/hole-lines/{hole_number}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
    responses={
        403: {"description": "ADMIN_REQUIRED"},
        404: {"description": "GOLF_COURSE_NOT_FOUND"},
        422: {"description": "HOLE_NOT_IN_COURSE"},
    },
)
async def reopen_hole(
    golf_course_id: UUID,
    hole_number: int,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[ReopenHoleUseCase, Depends(get_reopen_hole_use_case)],
):
    """Reabre el hoyo: se quita su línea y vuelve a recoger muestras. Sin línea, 204 igual."""
    if not current_user.is_admin:
        return _forbidden()
    try:
        await use_case.execute(
            ReopenHoleRequestDTO(golf_course_id=str(golf_course_id), hole_number=hole_number)
        )
    except GolfCourseNotFoundError:
        return _course_not_found()
    except HoleNotInCourseError:
        return _error(*_HOLE_NOT_IN_COURSE)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/admin/{golf_course_id}/hole-samples/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
    responses={
        403: {"description": "ADMIN_REQUIRED"},
        404: {"description": "GOLF_COURSE_NOT_FOUND or HOLE_SAMPLE_NOT_FOUND"},
    },
)
async def delete_hole_sample(
    golf_course_id: UUID,
    sample_id: UUID,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[DeleteHoleSampleUseCase, Depends(get_delete_hole_sample_use_case)],
):
    """Borra una muestra mala del campo (inventada, de otro hoyo): deja libre su hueco."""
    if not current_user.is_admin:
        return _forbidden()
    try:
        await use_case.execute(
            DeleteHoleSampleRequestDTO(golf_course_id=str(golf_course_id), sample_id=sample_id)
        )
    except GolfCourseNotFoundError:
        return _course_not_found()
    except HoleSampleNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "HOLE_SAMPLE_NOT_FOUND", "Hole sample not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin/hole-reviews",
    response_model=ListHoleReviewsResponseDTO,
    tags=["admin"],
    responses={403: {"description": "ADMIN_REQUIRED"}},
)
async def list_hole_reviews(
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[ListHoleReviewsUseCase, Depends(get_list_hole_reviews_use_case)],
):
    """
    Los campos con hoyos pendientes (con muestras y sin línea guardada): por hoyo,
    de menor a mayor, cuántas muestras tiene. `saved` es siempre false.
    """
    if not current_user.is_admin:
        return _forbidden()
    return await use_case.execute(ListHoleReviewsRequestDTO())


@router.get(
    "/admin/{golf_course_id}/hole-reviews",
    response_model=HoleReviewDTO,
    tags=["admin"],
    responses={
        403: {"description": "ADMIN_REQUIRED"},
        404: {"description": "GOLF_COURSE_NOT_FOUND"},
    },
)
async def get_hole_review(
    golf_course_id: UUID,
    current_user: Annotated[UserResponseDTO, Depends(get_current_user)],
    use_case: Annotated[GetHoleReviewUseCase, Depends(get_hole_review_use_case)],
):
    """
    Los 18 hoyos del campo para revisarlos: la ubicación del campo y, por hoyo,
    la línea guardada, la del mapa de OSM aprobado, todas las muestras (con su id
    y su barra, nunca de quién son) y los metros de cada barra.
    """
    if not current_user.is_admin:
        return _forbidden()
    try:
        return await use_case.execute(GetHoleReviewRequestDTO(golf_course_id=str(golf_course_id)))
    except GolfCourseNotFoundError:
        return _course_not_found()
