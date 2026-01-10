"""
Enrollment Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para gestión de inscripciones siguiendo Clean Architecture.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.config.dependencies import (
    get_cancel_enrollment_use_case,
    get_current_user,
    get_direct_enroll_player_use_case,
    get_handle_enrollment_use_case,
    get_list_enrollments_use_case,
    get_request_enrollment_use_case,
    get_set_custom_handicap_use_case,
    get_uow,  # User Unit of Work para obtener datos del usuario
    get_withdraw_enrollment_use_case,
)
from src.modules.competition.application.dto.enrollment_dto import (
    CancelEnrollmentRequestDTO,
    CancelEnrollmentResponseDTO,
    DirectEnrollPlayerRequestDTO,
    DirectEnrollPlayerResponseDTO,
    EnrolledUserDTO,
    EnrollmentResponseDTO,
    HandleEnrollmentRequestDTO,
    HandleEnrollmentResponseDTO,
    RequestEnrollmentRequestDTO,
    RequestEnrollmentResponseDTO,
    SetCustomHandicapRequestDTO,
    SetCustomHandicapResponseDTO,
    WithdrawEnrollmentRequestDTO,
    WithdrawEnrollmentResponseDTO,
)
from src.modules.competition.application.use_cases.cancel_enrollment_use_case import (
    CancelEnrollmentUseCase,
    EnrollmentNotFoundError as CancelEnrollmentNotFoundError,
    NotOwnerError as CancelNotOwnerError,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    AlreadyEnrolledError as DirectAlreadyEnrolledError,
    CompetitionNotActiveError as DirectCompetitionNotActiveError,
    CompetitionNotFoundError as DirectCompetitionNotFoundError,
    DirectEnrollPlayerUseCase,
    NotCreatorError as DirectNotCreatorError,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    CompetitionNotFoundError as HandleCompetitionNotFoundError,
    EnrollmentNotFoundError as HandleEnrollmentNotFoundError,
    HandleEnrollmentUseCase,
    NotCreatorError as HandleNotCreatorError,
)
from src.modules.competition.application.use_cases.list_enrollments_use_case import (
    CompetitionNotFoundError as ListCompetitionNotFoundError,
    ListEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    AlreadyEnrolledError as RequestAlreadyEnrolledError,
    CompetitionNotActiveError,
    CompetitionNotFoundError as RequestCompetitionNotFoundError,
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.set_custom_handicap_use_case import (
    CompetitionNotFoundError as HandicapCompetitionNotFoundError,
    EnrollmentNotFoundError as HandicapEnrollmentNotFoundError,
    NotCreatorError as HandicapNotCreatorError,
    SetCustomHandicapUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    EnrollmentNotFoundError as WithdrawEnrollmentNotFoundError,
    NotOwnerError as WithdrawNotOwnerError,
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.entities.enrollment import EnrollmentStateError
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
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

    RESPONSABILIDAD: Capa de presentación (API Layer)
    - Convertir entidades de dominio a DTOs
    - Calcular campos derivados para UI (user nested)
    - Formatear datos para el frontend
    """

    @staticmethod
    async def to_response_dto(
        enrollment, user_uow: UserUnitOfWorkInterface | None = None
    ) -> EnrollmentResponseDTO:
        """
        Convierte una entidad Enrollment a EnrollmentResponseDTO.

        Args:
            enrollment: Entidad de dominio
            user_uow: Unit of Work de usuarios para obtener datos del usuario (opcional)

        Returns:
            EnrollmentResponseDTO enriquecido con datos del usuario
        """
        # Obtener información del usuario (si user_uow es provisto)
        user_dto = None
        if user_uow:
            user_dto = await EnrollmentDTOMapper._get_user_dto(enrollment.user_id, user_uow)

        return EnrollmentResponseDTO(
            id=enrollment.id.value,
            competition_id=enrollment.competition_id.value,
            user_id=enrollment.user_id.value,
            user=user_dto,
            status=enrollment.status.value,
            team_id=enrollment.team_id,
            custom_handicap=enrollment.custom_handicap,
            created_at=enrollment.created_at,
            updated_at=enrollment.updated_at,
        )

    @staticmethod
    async def _get_user_dto(
        user_id: UserId,
        user_uow: UserUnitOfWorkInterface,
    ) -> EnrolledUserDTO | None:
        """
        Obtiene la información de un usuario inscrito.

        Args:
            user_id: ID del usuario
            user_uow: Unit of Work de usuarios

        Returns:
            EnrolledUserDTO con los datos del usuario, o None si no se encuentra
        """
        async with user_uow:
            user = await user_uow.users.find_by_id(user_id)

            if not user:
                logger.warning(f"User with id {user_id.value} not found")
                return None

            return EnrolledUserDTO(
                id=user.id.value,
                first_name=user.first_name,
                last_name=user.last_name,
                email=str(user.email),
                handicap=user.handicap.value if user.handicap else None,
                country_code=user.country_code.value if user.country_code else None,
                avatar_url=None,  # TODO: Implementar cuando tengamos sistema de avatares
            )


# ======================================================================================
# ENDPOINTS
# ======================================================================================


@router.post(
    "/competitions/{competition_id}/enrollments",
    response_model=RequestEnrollmentResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar inscripción",
    description="El usuario actual solicita inscribirse en una competición.",
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
            competition_id=competition_id, user_id=current_user.id
        )
        return await use_case.execute(request_dto)

    except RequestCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except CompetitionNotActiveError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RequestAlreadyEnrolledError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post(
    "/competitions/{competition_id}/enrollments/direct",
    response_model=DirectEnrollPlayerResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Inscripción directa por creador",
    description="El creador inscribe directamente a un jugador (estado APPROVED).",
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
            custom_handicap=request.custom_handicap,
        )
        creator_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, creator_id)

    except DirectCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DirectNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except DirectCompetitionNotActiveError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except DirectAlreadyEnrolledError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get(
    "/competitions/{competition_id}/enrollments",
    response_model=list[EnrollmentResponseDTO],
    summary="Listar inscripciones",
    description="Lista las inscripciones de una competición con filtros opcionales.",
)
async def list_enrollments(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),  # noqa: ARG001
    use_case: ListEnrollmentsUseCase = Depends(get_list_enrollments_use_case),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    status_filter: str | None = Query(None, alias="status", description="Filtrar por estado"),
):
    """
    Lista inscripciones de una competición.

    Filtros disponibles:
    - status: REQUESTED, APPROVED, REJECTED, CANCELLED, WITHDRAWN

    **Returns:**
    - Lista de enrollments con objeto `user` nested incluyendo:
      - id, first_name, last_name, email
      - handicap, country_code, avatar_url
    """
    try:
        enrollments = await use_case.execute(
            competition_id=str(competition_id), status=status_filter
        )

        # Convertir entidades a DTOs enriquecidos con datos de usuario
        result = []
        for enrollment in enrollments:
            dto = await EnrollmentDTOMapper.to_response_dto(enrollment, user_uow)
            result.append(dto)

        return result

    except ListCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/enrollments/{enrollment_id}/approve",
    response_model=HandleEnrollmentResponseDTO,
    summary="Aprobar inscripción",
    description="El creador aprueba una solicitud de inscripción.",
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
        request_dto = HandleEnrollmentRequestDTO(enrollment_id=enrollment_id, action="APPROVE")
        creator_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, creator_id)

    except HandleEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except HandleCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except HandleNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except EnrollmentStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/enrollments/{enrollment_id}/reject",
    response_model=HandleEnrollmentResponseDTO,
    summary="Rechazar inscripción",
    description="El creador rechaza una solicitud de inscripción.",
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
        request_dto = HandleEnrollmentRequestDTO(enrollment_id=enrollment_id, action="REJECT")
        creator_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, creator_id)

    except HandleEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except HandleCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except HandleNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except EnrollmentStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/enrollments/{enrollment_id}/cancel",
    response_model=CancelEnrollmentResponseDTO,
    summary="Cancelar inscripción",
    description="El usuario cancela su solicitud de inscripción o declina una invitación.",
)
async def cancel_enrollment(
    enrollment_id: UUID,
    reason: str | None = Query(None, description="Razón de la cancelación"),
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CancelEnrollmentUseCase = Depends(get_cancel_enrollment_use_case),
):
    """
    Cancela una solicitud de inscripción.

    Solo el dueño de la inscripción puede cancelarla.
    Solo válido desde estados REQUESTED o INVITED.
    """
    try:
        request_dto = CancelEnrollmentRequestDTO(enrollment_id=enrollment_id, reason=reason)
        user_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, user_id)

    except CancelEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except CancelNotOwnerError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except EnrollmentStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/enrollments/{enrollment_id}/withdraw",
    response_model=WithdrawEnrollmentResponseDTO,
    summary="Retirarse de competición",
    description="El usuario se retira después de haber sido aprobado.",
)
async def withdraw_enrollment(
    enrollment_id: UUID,
    reason: str | None = Query(None, description="Razón del retiro"),
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: WithdrawEnrollmentUseCase = Depends(get_withdraw_enrollment_use_case),
):
    """
    Retirarse de una competición.

    Solo el dueño de la inscripción puede retirarse.
    Solo válido desde estado APPROVED.
    """
    try:
        request_dto = WithdrawEnrollmentRequestDTO(enrollment_id=enrollment_id, reason=reason)
        user_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, user_id)

    except WithdrawEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except WithdrawNotOwnerError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except EnrollmentStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put(
    "/enrollments/{enrollment_id}/handicap",
    response_model=SetCustomHandicapResponseDTO,
    summary="Establecer hándicap personalizado",
    description="El creador establece un hándicap personalizado para un jugador.",
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
            enrollment_id=enrollment_id, custom_handicap=request.custom_handicap
        )
        creator_id = UserId(str(current_user.id))
        return await use_case.execute(request_dto, creator_id)

    except HandicapEnrollmentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except HandicapCompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except HandicapNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
