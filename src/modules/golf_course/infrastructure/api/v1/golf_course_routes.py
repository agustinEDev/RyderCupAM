"""
Golf Course Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para el módulo Golf Course siguiendo Clean Architecture.

Endpoints implementados (Sprint 1):
- POST   /api/v1/golf-courses/request           # Creator solicita nuevo campo
- GET    /api/v1/golf-courses/{id}              # Detalles de un campo
- GET    /api/v1/golf-courses                   # Listar campos (con filtros)
- GET    /api/v1/admin/golf-courses/pending     # Admin lista pendientes
- PUT    /api/v1/admin/golf-courses/{id}/approve # Admin aprueba
- PUT    /api/v1/admin/golf-courses/{id}/reject  # Admin rechaza

Endpoints v2.0.2 - Update Workflow (Opción A+):
- POST   /api/v1/admin/golf-courses             # Admin crea campo directo a APPROVED
- PUT    /api/v1/golf-courses/{id}              # Editar campo (con workflow de clones)
- PUT    /api/v1/admin/golf-courses/{clone_id}/approve-update # Admin aprueba update clone
- PUT    /api/v1/admin/golf-courses/{clone_id}/reject-update  # Admin rechaza update clone
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.config.dependencies import get_current_user, get_golf_course_uow
from src.modules.golf_course.application.dtos.golf_course_dtos import (
    ApproveGolfCourseRequestDTO,
    ApproveUpdateGolfCourseRequestDTO,
    GetGolfCourseByIdRequestDTO,
    ListApprovedGolfCoursesRequestDTO,
    ListPendingGolfCoursesRequestDTO,
    RejectGolfCourseRequestDTO,
    RejectUpdateGolfCourseRequestDTO,
    RequestGolfCourseRequestDTO,
    UpdateGolfCourseRequestDTO,
)
from src.modules.golf_course.application.use_cases.approve_golf_course_use_case import (
    ApproveGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.approve_update_golf_course_use_case import (
    ApproveUpdateGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.create_direct_golf_course_use_case import (
    CreateDirectGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.get_golf_course_by_id_use_case import (
    GetGolfCourseByIdUseCase,
)
from src.modules.golf_course.application.use_cases.list_approved_golf_courses_use_case import (
    ListApprovedGolfCoursesUseCase,
)
from src.modules.golf_course.application.use_cases.list_pending_golf_courses_use_case import (
    ListPendingGolfCoursesUseCase,
)
from src.modules.golf_course.application.use_cases.reject_golf_course_use_case import (
    RejectGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.reject_update_golf_course_use_case import (
    RejectUpdateGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.request_golf_course_use_case import (
    RequestGolfCourseUseCase,
)
from src.modules.golf_course.application.use_cases.update_golf_course_use_case import (
    UpdateGolfCourseUseCase,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.exceptions.business_rule_violation import BusinessRuleViolation

logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/golf-courses")


# ============================================================================
# Dependency Injection Helpers
# ============================================================================


def get_request_golf_course_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> RequestGolfCourseUseCase:
    """Dependency injection para RequestGolfCourseUseCase."""
    return RequestGolfCourseUseCase(uow)


def get_get_golf_course_by_id_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> GetGolfCourseByIdUseCase:
    """Dependency injection para GetGolfCourseByIdUseCase."""
    return GetGolfCourseByIdUseCase(uow)


def get_list_approved_golf_courses_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> ListApprovedGolfCoursesUseCase:
    """Dependency injection para ListApprovedGolfCoursesUseCase."""
    return ListApprovedGolfCoursesUseCase(uow)


def get_list_pending_golf_courses_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> ListPendingGolfCoursesUseCase:
    """Dependency injection para ListPendingGolfCoursesUseCase."""
    return ListPendingGolfCoursesUseCase(uow)


def get_approve_golf_course_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> ApproveGolfCourseUseCase:
    """Dependency injection para ApproveGolfCourseUseCase."""
    return ApproveGolfCourseUseCase(uow)


def get_reject_golf_course_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> RejectGolfCourseUseCase:
    """Dependency injection para RejectGolfCourseUseCase."""
    return RejectGolfCourseUseCase(uow)


def get_create_direct_golf_course_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> CreateDirectGolfCourseUseCase:
    """Dependency injection para CreateDirectGolfCourseUseCase."""
    return CreateDirectGolfCourseUseCase(uow)


def get_update_golf_course_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> UpdateGolfCourseUseCase:
    """Dependency injection para UpdateGolfCourseUseCase."""
    return UpdateGolfCourseUseCase(uow)


def get_approve_update_golf_course_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> ApproveUpdateGolfCourseUseCase:
    """Dependency injection para ApproveUpdateGolfCourseUseCase."""
    return ApproveUpdateGolfCourseUseCase(uow)


def get_reject_update_golf_course_use_case(
    uow: Annotated[GolfCourseUnitOfWorkInterface, Depends(get_golf_course_uow)],
) -> RejectUpdateGolfCourseUseCase:
    """Dependency injection para RejectUpdateGolfCourseUseCase."""
    return RejectUpdateGolfCourseUseCase(uow)


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post("/request", status_code=status.HTTP_201_CREATED)
async def request_golf_course(
    request_data: RequestGolfCourseRequestDTO,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[RequestGolfCourseUseCase, Depends(get_request_golf_course_use_case)],
):
    """
    Endpoint: Creator solicita un nuevo campo de golf.

    **Autenticación**: Requerida (cualquier usuario autenticado puede solicitar)
    **Authorization**: None (cualquier usuario puede crear solicitud)

    El campo se crea en estado PENDING_APPROVAL y debe ser aprobado por un Admin.

    **Request Body**:
    - name: Nombre del campo (3-200 caracteres)
    - country_code: Código ISO del país (ej: "ES", "US")
    - course_type: Tipo de campo ("STANDARD_18", "PITCH_AND_PUTT", "EXECUTIVE")
    - tees: Lista de 2-6 tees con ratings WHS
    - holes: Lista de 18 hoyos con par y stroke index únicos

    **Responses**:
    - 201: Campo solicitado exitosamente
    - 400: Datos inválidos (validación falló)
    - 401: No autenticado
    - 422: Validation error
    """
    try:
        # Crear UserId del usuario autenticado
        creator_id = UserId(str(current_user.id))

        response = await use_case.execute(request_data, creator_id)
        return response.golf_course

    except BusinessRuleViolation as e:
        logger.warning(f"Business rule violation: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Unexpected error in request_golf_course: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.get("/{golf_course_id}")
async def get_golf_course_by_id(
    golf_course_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[GetGolfCourseByIdUseCase, Depends(get_get_golf_course_by_id_use_case)],
):
    """
    Endpoint: Obtener detalles de un campo de golf por ID.

    **Autenticación**: Requerida
    **Authorization**: Según estado del campo:
    - APPROVED: Cualquier usuario autenticado
    - PENDING/REJECTED: Solo Admin o Creator (owner)

    **Path Parameters**:
    - golf_course_id: UUID del campo

    **Responses**:
    - 200: Campo encontrado
    - 401: No autenticado
    - 403: Sin permisos (campo no aprobado y no eres admin/creator)
    - 404: Campo no encontrado
    """
    try:
        request_dto = GetGolfCourseByIdRequestDTO(golf_course_id=str(golf_course_id))
        response = await use_case.execute(request_dto)

        golf_course = response.golf_course

        # Authorization: Verificar acceso según approval_status
        if golf_course.approval_status != ApprovalStatus.APPROVED.value:
            # Solo Admin o Creator pueden ver campos no aprobados
            is_admin = current_user.is_admin
            is_creator = str(golf_course.creator_id) == str(current_user.id)

            if not (is_admin or is_creator):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to view this golf course",
                )

        return golf_course

    except HTTPException:
        # Re-raise HTTPException as-is (403, 404, etc.) from None
        raise
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Unexpected error in get_golf_course_by_id: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.get("")
async def list_golf_courses(
    current_user: Annotated[User, Depends(get_current_user)],
    approved_use_case: Annotated[
        ListApprovedGolfCoursesUseCase, Depends(get_list_approved_golf_courses_use_case)
    ],
    approval_status: str | None = Query(
        None, description="Filter by approval status (APPROVED, PENDING_APPROVAL, REJECTED)"
    ),
):
    """
    Endpoint: Listar campos de golf con filtros opcionales.

    **Autenticación**: Requerida
    **Authorization**: Según filtro:
    - approval_status=APPROVED (default): Cualquier usuario
    - Otros estados: Solo Admin

    **Query Parameters**:
    - approval_status: Filtrar por estado (APPROVED, PENDING_APPROVAL, REJECTED)
      Default: APPROVED

    **Responses**:
    - 200: Lista de campos
    - 400: Valor inválido de approval_status
    - 401: No autenticado
    - 403: Sin permisos para ver estados no-aprobados
    """
    try:
        # Validar approval_status si se proporciona
        valid_statuses = ["APPROVED", "PENDING_APPROVAL", "REJECTED"]
        if approval_status is not None and approval_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid approval_status. Must be one of: {', '.join(valid_statuses)}",
            )

        # Por defecto, listar solo aprobados (público)
        if approval_status is None or approval_status == "APPROVED":
            request_dto = ListApprovedGolfCoursesRequestDTO()
            response = await approved_use_case.execute(request_dto)
            return {"golf_courses": response.golf_courses}

        # Otros estados válidos requieren permisos de Admin
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can view golf courses with non-approved status",
            )

        # TODO: Implementar filtros adicionales cuando se requieran
        # Por ahora, solo soportamos APPROVED
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only approval_status=APPROVED is currently supported",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in list_golf_courses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.put("/{golf_course_id}")
async def update_golf_course(
    golf_course_id: UUID,
    request_data: UpdateGolfCourseRequestDTO,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[UpdateGolfCourseUseCase, Depends(get_update_golf_course_use_case)],
):
    """
    Endpoint: Actualizar campo de golf existente.

    **Autenticación**: Requerida
    **Authorization**:
    - Admin: Puede editar cualquier campo (in-place, cambios inmediatos)
    - Creator: Solo sus propios campos

    **Workflow (Opción A+)**:
    - Admin edita APPROVED/PENDING → Actualiza in-place, cambios inmediatos
    - Creator edita APPROVED → Crea clone PENDING_APPROVAL, original permanece visible
    - Creator edita PENDING → Actualiza in-place
    - Campos REJECTED: NO editables (crear nueva solicitud)

    **Path Parameters**:
    - golf_course_id: UUID del campo a editar

    **Request Body**:
    - name: Nombre del campo (3-200 caracteres)
    - country_code: Código ISO del país (ej: "ES", "US")
    - course_type: Tipo de campo ("STANDARD_18", "PITCH_AND_PUTT", "EXECUTIVE")
    - tees: Lista de 2-6 tees con ratings WHS
    - holes: Lista de 18 hoyos con par y stroke index únicos

    **Responses**:
    - 200: Campo actualizado (puede incluir pending_update si se creó clone)
    - 400: Datos inválidos o campo REJECTED
    - 401: No autenticado
    - 403: Sin permisos (no eres admin ni creator)
    - 404: Campo no encontrado
    - 422: Validation error
    """
    try:
        from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

        golf_course_id_vo = GolfCourseId(str(golf_course_id))
        user_id = UserId(str(current_user.id))
        is_admin = current_user.is_admin

        response = await use_case.execute(
            golf_course_id=golf_course_id_vo,
            request=request_data,
            user_id=user_id,
            is_admin=is_admin,
        )

        return response

    except ValueError as e:
        error_str = str(e).lower()
        if "not found" in error_str:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
        if "permission" in error_str or "not have permission" in error_str:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from None
        if "rejected" in error_str or "cannot edit" in error_str:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

        logger.warning(f"Validation error in update_golf_course: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Unexpected error in update_golf_course: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================


@router.post("/admin", status_code=status.HTTP_201_CREATED, tags=["admin"])
async def create_direct_golf_course(
    request_data: RequestGolfCourseRequestDTO,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[
        CreateDirectGolfCourseUseCase, Depends(get_create_direct_golf_course_use_case)
    ],
):
    """
    Endpoint: Admin crea campo de golf directo a APPROVED.

    **Autenticación**: Requerida
    **Authorization**: Solo Admin

    A diferencia del endpoint /request, este crea el campo directamente
    en estado APPROVED sin necesidad de aprobación posterior.

    **Request Body**:
    - name: Nombre del campo (3-200 caracteres)
    - country_code: Código ISO del país (ej: "ES", "US")
    - course_type: Tipo de campo ("STANDARD_18", "PITCH_AND_PUTT", "EXECUTIVE")
    - tees: Lista de 2-6 tees con ratings WHS
    - holes: Lista de 18 hoyos con par y stroke index únicos

    **Responses**:
    - 201: Campo creado exitosamente (APPROVED)
    - 400: Datos inválidos
    - 401: No autenticado
    - 403: No eres Admin
    - 422: Validation error
    """
    # Authorization: Solo Admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create golf courses directly to APPROVED status",
        )

    try:
        creator_id = UserId(str(current_user.id))
        response = await use_case.execute(request_data, creator_id)

        return {
            "message": "Golf course created successfully (APPROVED)",
            "golf_course": response.golf_course,
        }

    except BusinessRuleViolation as e:
        logger.warning(f"Business rule violation: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Unexpected error in create_direct_golf_course: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.get("/admin/pending", tags=["admin"])
async def list_pending_golf_courses(
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[
        ListPendingGolfCoursesUseCase, Depends(get_list_pending_golf_courses_use_case)
    ],
):
    """
    Endpoint: Admin lista campos pendientes de aprobación.

    **Autenticación**: Requerida
    **Authorization**: Solo Admin

    **Responses**:
    - 200: Lista de campos pendientes
    - 401: No autenticado
    - 403: No eres Admin
    """
    # Authorization: Solo Admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this endpoint",
        )

    try:
        request_dto = ListPendingGolfCoursesRequestDTO()
        response = await use_case.execute(request_dto)
        return {"golf_courses": response.golf_courses}

    except Exception as e:
        logger.error(f"Unexpected error in list_pending_golf_courses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.put("/admin/{golf_course_id}/approve", tags=["admin"])
async def approve_golf_course(
    golf_course_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[ApproveGolfCourseUseCase, Depends(get_approve_golf_course_use_case)],
):
    """
    Endpoint: Admin aprueba un campo de golf.

    **Autenticación**: Requerida
    **Authorization**: Solo Admin

    El campo pasa de PENDING_APPROVAL → APPROVED y dispara un evento
    que envía email bilingüe (ES/EN) al Creator.

    **Path Parameters**:
    - golf_course_id: UUID del campo a aprobar

    **Responses**:
    - 200: Campo aprobado exitosamente
    - 401: No autenticado
    - 403: No eres Admin
    - 404: Campo no encontrado
    - 400: Estado inválido (no se puede aprobar)
    """
    # Authorization: Solo Admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can approve golf courses",
        )

    try:
        request_dto = ApproveGolfCourseRequestDTO(golf_course_id=str(golf_course_id))
        response = await use_case.execute(request_dto)

        return {
            "message": "Golf course approved successfully",
            "golf_course": response.golf_course,
        }

    except ValueError as e:
        error_str = str(e).lower()
        if "not found" in error_str:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
        if "cannot approve" in error_str or "only pending" in error_str:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Unexpected error in approve_golf_course: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.put("/admin/{golf_course_id}/reject", tags=["admin"])
async def reject_golf_course(
    golf_course_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[RejectGolfCourseUseCase, Depends(get_reject_golf_course_use_case)],
    reason: str = Query(..., min_length=10, max_length=500, description="Rejection reason"),
):
    """
    Endpoint: Admin rechaza un campo de golf.

    **Autenticación**: Requerida
    **Authorization**: Solo Admin

    El campo pasa de PENDING_APPROVAL → REJECTED y dispara un evento
    que envía email bilingüe (ES/EN) al Creator con la razón del rechazo.

    **Path Parameters**:
    - golf_course_id: UUID del campo a rechazar

    **Query Parameters**:
    - reason: Razón del rechazo (10-500 caracteres)

    **Responses**:
    - 200: Campo rechazado exitosamente
    - 401: No autenticado
    - 403: No eres Admin
    - 404: Campo no encontrado
    - 400: Estado inválido o razón inválida
    """
    # Authorization: Solo Admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can reject golf courses",
        )

    try:
        request_dto = RejectGolfCourseRequestDTO(golf_course_id=str(golf_course_id), reason=reason)
        response = await use_case.execute(request_dto)

        return {
            "message": "Golf course rejected successfully",
            "golf_course": response.golf_course,
        }

    except ValueError as e:
        error_str = str(e).lower()
        if "not found" in error_str:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
        if "cannot reject" in error_str or "only pending" in error_str:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
        if "reason" in error_str and ("10" in error_str or "500" in error_str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Unexpected error in reject_golf_course: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.put("/admin/{clone_id}/approve-update", tags=["admin"])
async def approve_update_golf_course(
    clone_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[
        ApproveUpdateGolfCourseUseCase, Depends(get_approve_update_golf_course_use_case)
    ],
):
    """
    Endpoint: Admin aprueba un update proposal (clone) de campo de golf.

    **Autenticación**: Requerida
    **Authorization**: Solo Admin

    **Workflow**:
    1. Busca el clone por ID
    2. Verifica que sea un clone válido (tiene original_golf_course_id)
    3. Busca el campo original
    4. Aplica todos los cambios del clone al original
    5. Elimina el clone
    6. Marca original como is_pending_update=FALSE
    7. Retorna el original actualizado

    **Path Parameters**:
    - clone_id: UUID del clone a aprobar (NO el original)

    **Responses**:
    - 200: Update aprobado, cambios aplicados al original
    - 400: Clone inválido o no es un clone
    - 401: No autenticado
    - 403: No eres Admin
    - 404: Clone o campo original no encontrado
    """
    # Authorization: Solo Admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can approve golf course updates",
        )

    try:
        request_dto = ApproveUpdateGolfCourseRequestDTO(clone_id=str(clone_id))
        response = await use_case.execute(request_dto)

        return {
            "message": "Golf course update approved successfully",
            "updated_golf_course": response.updated_golf_course,
            "applied_changes_from": response.applied_changes_from,
        }

    except ValueError as e:
        error_str = str(e).lower()
        if "not found" in error_str:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
        if "not a clone" in error_str or "does not have" in error_str:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Unexpected error in approve_update_golf_course: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None


@router.put("/admin/{clone_id}/reject-update", tags=["admin"])
async def reject_update_golf_course(
    clone_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: Annotated[
        RejectUpdateGolfCourseUseCase, Depends(get_reject_update_golf_course_use_case)
    ],
):
    """
    Endpoint: Admin rechaza un update proposal (clone) de campo de golf.

    **Autenticación**: Requerida
    **Authorization**: Solo Admin

    **Workflow**:
    1. Busca el clone por ID
    2. Verifica que sea un clone válido (tiene original_golf_course_id)
    3. Busca el campo original
    4. Elimina el clone (rechazado)
    5. Marca original como is_pending_update=FALSE (clear mark)
    6. Retorna el original sin cambios

    **Path Parameters**:
    - clone_id: UUID del clone a rechazar (NO el original)

    **Responses**:
    - 200: Update rechazado, clone eliminado, original sin cambios
    - 400: Clone inválido o no es un clone
    - 401: No autenticado
    - 403: No eres Admin
    - 404: Clone o campo original no encontrado
    """
    # Authorization: Solo Admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can reject golf course updates",
        )

    try:
        request_dto = RejectUpdateGolfCourseRequestDTO(clone_id=str(clone_id))
        response = await use_case.execute(request_dto)

        return {
            "message": "Golf course update rejected successfully",
            "original_golf_course": response.original_golf_course,
            "rejected_clone_id": response.rejected_clone_id,
        }

    except ValueError as e:
        error_str = str(e).lower()
        if "not found" in error_str:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from None
        if "not a clone" in error_str or "does not have" in error_str:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
    except Exception as e:
        logger.error(f"Unexpected error in reject_update_golf_course: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None
