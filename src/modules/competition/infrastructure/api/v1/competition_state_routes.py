"""Competition State Transition Routes - activate, close, start, complete, cancel."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.config.dependencies import (
    get_activate_competition_use_case,
    get_cancel_competition_use_case,
    get_close_enrollments_use_case,
    get_competition_uow,
    get_complete_competition_use_case,
    get_current_user,
    get_reopen_enrollments_use_case,
    get_revert_competition_status_use_case,
    get_start_competition_use_case,
    get_uow,
)
from src.config.rate_limit import limiter
from src.modules.competition.application.dto.competition_dto import (
    ActivateCompetitionRequestDTO,
    CancelCompetitionRequestDTO,
    CloseEnrollmentsRequestDTO,
    CompetitionResponseDTO,
    CompleteCompetitionRequestDTO,
    ReopenEnrollmentsRequestDTO,
    RevertCompetitionStatusRequestDTO,
    StartCompetitionRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.mappers.competition_mapper import (
    CompetitionDTOMapper,
)
from src.modules.competition.application.use_cases.activate_competition_use_case import (
    ActivateCompetitionUseCase,
    CompetitionNotFoundError as ActivateNotFoundError,
    NotCompetitionCreatorError as ActivateNotCreatorError,
)
from src.modules.competition.application.use_cases.cancel_competition_use_case import (
    CancelCompetitionUseCase,
    CompetitionNotFoundError as CancelNotFoundError,
    NotCompetitionCreatorError as CancelNotCreatorError,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
    CompetitionNotFoundError as CloseNotFoundError,
    NotCompetitionCreatorError as CloseNotCreatorError,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.revert_competition_status_use_case import (
    RevertCompetitionStatusUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    CompetitionNotFoundError as StartNotFoundError,
    NotCompetitionCreatorError as StartNotCreatorError,
    StartCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import (
    CompetitionStateError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Aliases for shared exceptions
CompleteNotFoundError = CompetitionNotFoundError
CompleteNotCreatorError = NotCompetitionCreatorError
RevertNotFoundError = CompetitionNotFoundError
RevertNotCreatorError = NotCompetitionCreatorError
ReopenNotFoundError = CompetitionNotFoundError
ReopenNotCreatorError = NotCompetitionCreatorError

router = APIRouter()


# ======================================================================================
# STATE TRANSITION ENDPOINTS
# ======================================================================================


@router.post(
    "/{competition_id}/activate",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Activar competición (DRAFT → ACTIVE)",
    description="Activa una competición para abrir inscripciones. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
@limiter.limit("10/minute")
async def activate_competition(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ActivateCompetitionUseCase = Depends(get_activate_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Transición de estado: DRAFT → ACTIVE."""
    try:
        current_user_id = UserId(str(current_user.id))

        request_dto = ActivateCompetitionRequestDTO(competition_id=competition_id)
        await use_case.execute(request_dto, current_user_id)

        competition_vo_id = CompetitionId(competition_id)
        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except ActivateNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ActivateNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/{competition_id}/close-enrollments",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Cerrar inscripciones (ACTIVE → CLOSED)",
    description="Cierra las inscripciones de una competición. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
@limiter.limit("10/minute")
async def close_enrollments(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CloseEnrollmentsUseCase = Depends(get_close_enrollments_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Transición de estado: ACTIVE → CLOSED."""
    try:
        current_user_id = UserId(str(current_user.id))

        request_dto = CloseEnrollmentsRequestDTO(competition_id=competition_id)
        await use_case.execute(request_dto, current_user_id)

        competition_vo_id = CompetitionId(competition_id)
        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except CloseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except CloseNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/{competition_id}/start",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Iniciar competición (CLOSED → IN_PROGRESS)",
    description="Inicia el torneo. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
@limiter.limit("10/minute")
async def start_competition(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: StartCompetitionUseCase = Depends(get_start_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Transición de estado: CLOSED → IN_PROGRESS."""
    try:
        current_user_id = UserId(str(current_user.id))

        request_dto = StartCompetitionRequestDTO(competition_id=competition_id)
        await use_case.execute(request_dto, current_user_id)

        competition_vo_id = CompetitionId(competition_id)
        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except StartNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except StartNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/{competition_id}/complete",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Completar competición (IN_PROGRESS → COMPLETED)",
    description="Finaliza el torneo. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
@limiter.limit("10/minute")
async def complete_competition(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CompleteCompetitionUseCase = Depends(get_complete_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Transición de estado: IN_PROGRESS → COMPLETED."""
    try:
        current_user_id = UserId(str(current_user.id))

        request_dto = CompleteCompetitionRequestDTO(competition_id=competition_id)
        await use_case.execute(request_dto, current_user_id)

        competition_vo_id = CompetitionId(competition_id)
        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except CompleteNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except CompleteNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.put(
    "/{competition_id}/revert-status",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Revertir competición a CLOSED (IN_PROGRESS → CLOSED)",
    description="Revierte una competición para corregir el schedule. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
@limiter.limit("10/minute")
async def revert_competition_status(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: RevertCompetitionStatusUseCase = Depends(get_revert_competition_status_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Transición de estado: IN_PROGRESS → CLOSED."""
    try:
        current_user_id = UserId(str(current_user.id))

        request_dto = RevertCompetitionStatusRequestDTO(competition_id=competition_id)
        await use_case.execute(request_dto, current_user_id)

        competition_vo_id = CompetitionId(competition_id)
        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except RevertNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RevertNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/{competition_id}/reopen-enrollments",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Reabrir inscripciones (CLOSED → ACTIVE)",
    description="Reabre inscripciones para añadir o modificar jugadores. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
@limiter.limit("10/minute")
async def reopen_enrollments(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ReopenEnrollmentsUseCase = Depends(get_reopen_enrollments_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Transición de estado: CLOSED → ACTIVE."""
    try:
        current_user_id = UserId(str(current_user.id))

        request_dto = ReopenEnrollmentsRequestDTO(competition_id=competition_id)
        await use_case.execute(request_dto, current_user_id)

        competition_vo_id = CompetitionId(competition_id)
        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except ReopenNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ReopenNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/{competition_id}/cancel",
    response_model=CompetitionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Cancelar competición (cualquier estado → CANCELLED)",
    description="Cancela una competición. Solo el creador.",
    tags=["Competitions - State Transitions"],
)
@limiter.limit("10/minute")
async def cancel_competition(
    request: Request,  # noqa: ARG001 - Required by @limiter decorator
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CancelCompetitionUseCase = Depends(get_cancel_competition_use_case),
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
):
    """Transición de estado: cualquier estado → CANCELLED."""
    try:
        current_user_id = UserId(str(current_user.id))

        request_dto = CancelCompetitionRequestDTO(competition_id=competition_id)
        await use_case.execute(request_dto, current_user_id)

        competition_vo_id = CompetitionId(competition_id)
        async with uow, user_uow:
            competition = await uow.competitions.find_by_id(competition_vo_id)
            dto = await CompetitionDTOMapper.to_response_dto(
                competition, current_user_id, uow, user_uow
            )

        return dto

    except CancelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except CancelNotCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except (CompetitionStateError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
