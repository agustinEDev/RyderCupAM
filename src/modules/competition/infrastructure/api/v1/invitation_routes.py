"""
Invitation Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para gestion de invitaciones siguiendo Clean Architecture.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field

from src.config.dependencies import (
    get_current_user,
    get_list_competition_invitations_use_case,
    get_list_my_invitations_use_case,
    get_respond_to_invitation_use_case,
    get_send_invitation_by_email_use_case,
    get_send_invitation_by_user_id_use_case,
)
from src.modules.competition.application.dto.invitation_dto import (
    PaginatedInvitationResponseDTO,
    RespondInvitationRequestDTO,
    RespondInvitationResponseDTO,
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    InvitationNotFoundError,
    InviteeNotFoundError,
    NotCompetitionCreatorError,
    NotInviteeError,
)
from src.modules.competition.application.use_cases.list_competition_invitations_use_case import (
    ListCompetitionInvitationsUseCase,
)
from src.modules.competition.application.use_cases.list_my_invitations_use_case import (
    ListMyInvitationsUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_email_use_case import (
    SendInvitationByEmailUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.domain.exceptions.competition_violations import (
    AlreadyEnrolledInvitationViolation,
    CompetitionFullViolation,
    DuplicateInvitationViolation,
    InvalidInvitationStatusViolation,
    InvitationCompetitionStatusViolation,
    InvitationExpiredViolation,
    InvitationRateLimitViolation,
    SelfInvitationViolation,
)
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.user.application.dto.user_dto import UserResponseDTO


def _validate_status_filter(status_filter: str | None) -> str | None:
    """Valida el status filter contra InvitationStatus antes de pasar al use case."""
    if status_filter is None:
        return None
    try:
        InvitationStatus(status_filter)
        return status_filter
    except ValueError:
        valid = [s.value for s in InvitationStatus]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status filter: '{status_filter}'. Valid values: {valid}",
        )

logger = logging.getLogger(__name__)
router = APIRouter()


# ======================================================================================
# REQUEST BODY MODELS (Presentation Layer)
# ======================================================================================


class SendInvitationByUserIdBody(BaseModel):
    """Body para enviar invitacion por user_id."""

    invitee_user_id: UUID
    personal_message: str | None = Field(None, max_length=500)


class SendInvitationByEmailBody(BaseModel):
    """Body para enviar invitacion por email."""

    invitee_email: EmailStr
    personal_message: str | None = Field(None, max_length=500)


class RespondInvitationBody(BaseModel):
    """Body para responder a una invitacion."""

    action: str = Field(
        ..., description="Action to perform: ACCEPT or DECLINE", pattern="^(ACCEPT|DECLINE)$"
    )


# ======================================================================================
# ENDPOINTS
# ======================================================================================


@router.post(
    "/competitions/{competition_id}/invitations",
    status_code=status.HTTP_201_CREATED,
    summary="Send invitation by user ID",
    description="Creator sends an invitation to a registered user by their user ID.",
)
async def send_invitation_by_user_id(
    competition_id: UUID,
    body: SendInvitationByUserIdBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SendInvitationByUserIdUseCase = Depends(
        get_send_invitation_by_user_id_use_case
    ),
):
    try:
        request_dto = SendInvitationByUserIdRequestDTO(
            competition_id=competition_id,
            inviter_id=current_user.id,
            invitee_user_id=body.invitee_user_id,
            personal_message=body.personal_message,
        )
        return await use_case.execute(request_dto)

    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except InviteeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except SelfInvitationViolation as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except AlreadyEnrolledInvitationViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except DuplicateInvitationViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InvitationRateLimitViolation as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)
        ) from e
    except InvitationCompetitionStatusViolation as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e


@router.post(
    "/competitions/{competition_id}/invitations/by-email",
    status_code=status.HTTP_201_CREATED,
    summary="Send invitation by email",
    description="Creator sends an invitation to an email address (registered or not).",
)
async def send_invitation_by_email(
    competition_id: UUID,
    body: SendInvitationByEmailBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SendInvitationByEmailUseCase = Depends(
        get_send_invitation_by_email_use_case
    ),
):
    try:
        request_dto = SendInvitationByEmailRequestDTO(
            competition_id=competition_id,
            inviter_id=current_user.id,
            invitee_email=body.invitee_email,
            personal_message=body.personal_message,
        )
        return await use_case.execute(request_dto)

    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except SelfInvitationViolation as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except AlreadyEnrolledInvitationViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except DuplicateInvitationViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InvitationRateLimitViolation as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)
        ) from e
    except InvitationCompetitionStatusViolation as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e


@router.get(
    "/invitations/me",
    response_model=PaginatedInvitationResponseDTO,
    summary="List my invitations",
    description="List invitations received by the authenticated user.",
)
async def list_my_invitations(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListMyInvitationsUseCase = Depends(get_list_my_invitations_use_case),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    validated_status = _validate_status_filter(status_filter)
    return await use_case.execute(
        user_id=str(current_user.id),
        status_filter=validated_status,
        page=page,
        limit=limit,
    )


@router.post(
    "/invitations/{invitation_id}/respond",
    response_model=RespondInvitationResponseDTO,
    summary="Respond to invitation",
    description="Accept or decline an invitation.",
)
async def respond_to_invitation(
    invitation_id: UUID,
    body: RespondInvitationBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: RespondToInvitationUseCase = Depends(get_respond_to_invitation_use_case),
):
    try:
        request_dto = RespondInvitationRequestDTO(
            invitation_id=invitation_id,
            user_id=current_user.id,
            action=body.action,
        )
        return await use_case.execute(request_dto)

    except InvitationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotInviteeError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except InvalidInvitationStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InvitationExpiredViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InvitationCompetitionStatusViolation as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except CompetitionFullViolation as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get(
    "/competitions/{competition_id}/invitations",
    response_model=PaginatedInvitationResponseDTO,
    summary="List competition invitations",
    description="List invitations sent for a competition (creator/admin only).",
)
async def list_competition_invitations(
    competition_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListCompetitionInvitationsUseCase = Depends(
        get_list_competition_invitations_use_case
    ),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        validated_status = _validate_status_filter(status_filter)
        return await use_case.execute(
            competition_id=str(competition_id),
            current_user_id=str(current_user.id),
            is_admin=current_user.is_admin,
            status_filter=validated_status,
            page=page,
            limit=limit,
        )

    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotCompetitionCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
