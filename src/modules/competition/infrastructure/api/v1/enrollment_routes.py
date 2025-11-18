# -*- coding: utf-8 -*-
"""
Enrollment Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para gestión de inscripciones siguiendo Clean Architecture.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from uuid import UUID

from src.config.dependencies import (
    get_current_user,
    get_competition_uow,
    get_request_enrollment_use_case,
    get_direct_enroll_player_use_case,
    get_handle_enrollment_use_case,
    get_cancel_enrollment_use_case,
    get_withdraw_enrollment_use_case,
    get_set_custom_handicap_use_case,
    get_list_enrollments_use_case,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.competition.application.dto.enrollment_dto import (
    RequestEnrollmentRequestDTO,
    RequestEnrollmentResponseDTO,
    DirectEnrollPlayerRequestDTO,
    DirectEnrollPlayerResponseDTO,
    HandleEnrollmentRequestDTO,
    HandleEnrollmentResponseDTO,
    CancelEnrollmentRequestDTO,
    CancelEnrollmentResponseDTO,
    WithdrawEnrollmentRequestDTO,
    WithdrawEnrollmentResponseDTO,
    SetCustomHandicapRequestDTO,
    SetCustomHandicapResponseDTO,
    EnrollmentResponseDTO,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
    CompetitionNotFoundError as RequestCompetitionNotFoundError,
    CompetitionNotActiveError,
    AlreadyEnrolledError as RequestAlreadyEnrolledError,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
    CompetitionNotFoundError as DirectCompetitionNotFoundError,
    NotCreatorError as DirectNotCreatorError,
    CompetitionNotActiveError as DirectCompetitionNotActiveError,
    AlreadyEnrolledError as DirectAlreadyEnrolledError,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
    EnrollmentNotFoundError as HandleEnrollmentNotFoundError,
    CompetitionNotFoundError as HandleCompetitionNotFoundError,
    NotCreatorError as HandleNotCreatorError,
    InvalidActionError,
)
from src.modules.competition.application.use_cases.cancel_enrollment_use_case import (
    CancelEnrollmentUseCase,
    EnrollmentNotFoundError as CancelEnrollmentNotFoundError,
    NotOwnerError as CancelNotOwnerError,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
    EnrollmentNotFoundError as WithdrawEnrollmentNotFoundError,
    NotOwnerError as WithdrawNotOwnerError,
)
from src.modules.competition.application.use_cases.set_custom_handicap_use_case import (
    SetCustomHandicapUseCase,
    EnrollmentNotFoundError as HandicapEnrollmentNotFoundError,
    CompetitionNotFoundError as HandicapCompetitionNotFoundError,
    NotCreatorError as HandicapNotCreatorError,
)
from src.modules.competition.application.use_cases.list_enrollments_use_case import (
    ListEnrollmentsUseCase,
    CompetitionNotFoundError as ListCompetitionNotFoundError,
)
from src.modules.competition.domain.entities.enrollment import EnrollmentStateError
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)
router = APIRouter()


# ======================================================================================
# HELPER: EnrollmentDTOMapper (Presentation Layer Logic)
# ======================================================================================

class EnrollmentDTOMapper:
    """
    Mapper para convertir entidades Enrollment a DTOs de presentación.
    """

    @staticmethod
    def to_response_dto(enrollment) -> EnrollmentResponseDTO:
        """
        Convierte una entidad Enrollment a EnrollmentResponseDTO.
        """
        return EnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            status=enrollment.status.value,
            team_id=enrollment.team_id,
            custom_handicap=enrollment.custom_handicap,
            created_at=enrollment.created_at,
            updated_at=enrollment.updated_at
        )


# ======================================================================================
# ENDPOINTS
# ======================================================================================

@router.post(
    "/competitions/{competition_id}/enrollments",
    response_model=RequestEnrollmentResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar inscripción",
    description="El usuario actual solicita inscribirse en una competición."
)
async def request_enrollment(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: RequestEnrollmentUseCase = Depends(get_request_enrollment_use_case),
):
    """
    Solicita inscripción en una competición.

    El usuario actual se inscribe en la competición especificada.
    La inscripción queda en estado REQUESTED hasta que el creador la apruebe.
    """
    try:
        request_dto = RequestEnrollmentRequestDTO(
            competition_id=competition_id,
            user_id=current_user.id
        )
        return await use_case.execute(request_dto)

    except RequestCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CompetitionNotActiveError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RequestAlreadyEnrolledError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/competitions/{competition_id}/enrollments/direct",
    response_model=DirectEnrollPlayerResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Inscripción directa por creador",
    description="El creador inscribe directamente a un jugador (estado APPROVED)."
)
async def direct_enroll_player(
    competition_id: UUID,
    request: DirectEnrollPlayerRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: DirectEnrollPlayerUseCase = Depends(get_direct_enroll_player_use_case),
):
    """
    Inscripción directa por el creador.

    Solo el creador de la competición puede usar este endpoint.
    El jugador queda directamente en estado APPROVED.
    """
    try:
        # Asegurar que el competition_id del path coincida
        request_dto = DirectEnrollPlayerRequestDTO(
            competition_id=competition_id,
            user_id=request.user_id,
            custom_handicap=request.custom_handicap
        )
        creator_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, creator_id)

    except DirectCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DirectNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except DirectCompetitionNotActiveError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DirectAlreadyEnrolledError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get(
    "/competitions/{competition_id}/enrollments",
    response_model=List[EnrollmentResponseDTO],
    summary="Listar inscripciones",
    description="Lista las inscripciones de una competición con filtros opcionales."
)
async def list_enrollments(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListEnrollmentsUseCase = Depends(get_list_enrollments_use_case),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado"),
):
    """
    Lista inscripciones de una competición.

    Filtros disponibles:
    - status: REQUESTED, APPROVED, REJECTED, CANCELLED, WITHDRAWN
    """
    try:
        enrollments = await use_case.execute(
            competition_id=str(competition_id),
            status=status_filter
        )

        return [EnrollmentDTOMapper.to_response_dto(e) for e in enrollments]

    except ListCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/enrollments/{enrollment_id}/approve",
    response_model=HandleEnrollmentResponseDTO,
    summary="Aprobar inscripción",
    description="El creador aprueba una solicitud de inscripción."
)
async def approve_enrollment(
    enrollment_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: HandleEnrollmentUseCase = Depends(get_handle_enrollment_use_case),
):
    """
    Aprueba una solicitud de inscripción.

    Solo el creador de la competición puede aprobar.
    """
    try:
        request_dto = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment_id,
            action="APPROVE"
        )
        creator_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, creator_id)

    except HandleEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HandleCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HandleNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EnrollmentStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/enrollments/{enrollment_id}/reject",
    response_model=HandleEnrollmentResponseDTO,
    summary="Rechazar inscripción",
    description="El creador rechaza una solicitud de inscripción."
)
async def reject_enrollment(
    enrollment_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: HandleEnrollmentUseCase = Depends(get_handle_enrollment_use_case),
):
    """
    Rechaza una solicitud de inscripción.

    Solo el creador de la competición puede rechazar.
    """
    try:
        request_dto = HandleEnrollmentRequestDTO(
            enrollment_id=enrollment_id,
            action="REJECT"
        )
        creator_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, creator_id)

    except HandleEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HandleCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HandleNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EnrollmentStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/enrollments/{enrollment_id}/cancel",
    response_model=CancelEnrollmentResponseDTO,
    summary="Cancelar inscripción",
    description="El usuario cancela su solicitud de inscripción o declina una invitación."
)
async def cancel_enrollment(
    enrollment_id: UUID,
    reason: Optional[str] = Query(None, description="Razón de la cancelación"),
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CancelEnrollmentUseCase = Depends(get_cancel_enrollment_use_case),
):
    """
    Cancela una solicitud de inscripción.

    Solo el dueño de la inscripción puede cancelarla.
    Solo válido desde estados REQUESTED o INVITED.
    """
    try:
        request_dto = CancelEnrollmentRequestDTO(
            enrollment_id=enrollment_id,
            reason=reason
        )
        user_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, user_id)

    except CancelEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CancelNotOwnerError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EnrollmentStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/enrollments/{enrollment_id}/withdraw",
    response_model=WithdrawEnrollmentResponseDTO,
    summary="Retirarse de competición",
    description="El usuario se retira después de haber sido aprobado."
)
async def withdraw_enrollment(
    enrollment_id: UUID,
    reason: Optional[str] = Query(None, description="Razón del retiro"),
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: WithdrawEnrollmentUseCase = Depends(get_withdraw_enrollment_use_case),
):
    """
    Retirarse de una competición.

    Solo el dueño de la inscripción puede retirarse.
    Solo válido desde estado APPROVED.
    """
    try:
        request_dto = WithdrawEnrollmentRequestDTO(
            enrollment_id=enrollment_id,
            reason=reason
        )
        user_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, user_id)

    except WithdrawEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WithdrawNotOwnerError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EnrollmentStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/enrollments/{enrollment_id}/handicap",
    response_model=SetCustomHandicapResponseDTO,
    summary="Establecer hándicap personalizado",
    description="El creador establece un hándicap personalizado para un jugador."
)
async def set_custom_handicap(
    enrollment_id: UUID,
    request: SetCustomHandicapRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SetCustomHandicapUseCase = Depends(get_set_custom_handicap_use_case),
):
    """
    Establece un hándicap personalizado.

    Solo el creador de la competición puede establecer hándicaps personalizados.
    El valor debe estar entre -10.0 y 54.0.
    """
    try:
        # Asegurar que el enrollment_id del path se use
        request_dto = SetCustomHandicapRequestDTO(
            enrollment_id=enrollment_id,
            custom_handicap=request.custom_handicap
        )
        creator_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, creator_id)

    except HandicapEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HandicapCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except HandicapNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
