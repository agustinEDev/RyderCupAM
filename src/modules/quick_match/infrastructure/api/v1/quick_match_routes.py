"""
Quick Match Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para gestion de partidas rapidas siguiendo Clean Architecture.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator

from src.config.dependencies import (
    get_add_friend_to_quick_match_use_case,
    get_add_guest_to_quick_match_use_case,
    get_cancel_quick_match_use_case,
    get_complete_quick_match_use_case,
    get_create_quick_match_use_case,
    get_current_user,
    get_get_quick_match_use_case,
    get_list_my_quick_matches_use_case,
    get_remove_quick_match_participant_use_case,
    get_start_quick_match_use_case,
    get_submit_quick_match_hole_score_use_case,
    get_submit_quick_match_proxy_hole_score_use_case,
)
from src.config.rate_limit import limiter
from src.modules.quick_match.application.dto.quick_match_dto import (
    MAX_NAME_LENGTH,
    MAX_SCORERS,
    AddGuestParticipantRequestDTO,
    AddParticipantRequestDTO,
    CreateQuickMatchRequestDTO,
    HoleScoreResponseDTO,
    PaginatedQuickMatchResponseDTO,
    QuickMatchDetailResponseDTO,
    QuickMatchResponseDTO,
    RemoveParticipantRequestDTO,
    StartQuickMatchRequestDTO,
    SubmitHoleScoreRequestDTO,
    SubmitProxyHoleScoreRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    FriendUserNotFoundError,
    GolfCourseNotApprovedError,
    GolfCourseNotFoundError,
    InvalidTeeSelectionError,
    NotAScorerError,
    NotAuthorizedToRemoveError,
    NotFriendsError,
    NotQuickMatchCreatorError,
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
    TargetParticipantNotFoundError,
)
from src.modules.quick_match.application.use_cases.add_friend_to_quick_match_use_case import (
    AddFriendToQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.add_guest_to_quick_match_use_case import (
    AddGuestToQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.cancel_quick_match_use_case import (
    CancelQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.complete_quick_match_use_case import (
    CompleteQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.create_quick_match_use_case import (
    CreateQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.get_quick_match_use_case import (
    GetQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.list_my_quick_matches_use_case import (
    ListMyQuickMatchesUseCase,
)
from src.modules.quick_match.application.use_cases.remove_participant_use_case import (
    RemoveParticipantUseCase,
)
from src.modules.quick_match.application.use_cases.start_quick_match_use_case import (
    StartQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.submit_hole_score_use_case import (
    SubmitQuickMatchHoleScoreUseCase,
)
from src.modules.quick_match.application.use_cases.submit_proxy_hole_score_use_case import (
    SubmitProxyHoleScoreUseCase,
)
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    CreatorCannotBeRemovedViolation,
    DuplicateParticipantViolation,
    IncompleteRosterViolation,
    InvalidAllowanceViolation,
    InvalidHoleScoreViolation,
    InvalidQuickMatchStatusViolation,
    InvalidScorerConfigurationViolation,
    InvalidTeamAssignmentViolation,
    NotAssignedScorerViolation,
    NotQuickMatchParticipantViolation,
    QuickMatchFullViolation,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO

logger = logging.getLogger(__name__)
router = APIRouter()


# ======================================================================================
# REQUEST BODY MODELS (Presentation Layer)
# ======================================================================================


TEE_CATEGORY_PATTERN = "^(CHAMPIONSHIP|AMATEUR|SENIOR|FORWARD|JUNIOR)$"
TEE_GENDER_PATTERN = "^(MALE|FEMALE)$"


class CreateQuickMatchBody(BaseModel):
    """Body para crear una partida rapida. Exactamente uno de match_format/scoring_format."""

    golf_course_id: UUID
    match_format: str | None = Field(None, pattern="^(SINGLES|FOURBALL|FOURSOMES)$")
    scoring_format: str | None = Field(None, pattern="^(MEDAL|STABLEFORD)$")
    name: str | None = Field(None, max_length=MAX_NAME_LENGTH)
    allowance_percentage: int | None = Field(None, ge=50, le=100)
    creator_tee_category: str | None = Field(None, pattern=TEE_CATEGORY_PATTERN)
    creator_tee_gender: str | None = Field(None, pattern=TEE_GENDER_PATTERN)

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _exactly_one_format(self) -> "CreateQuickMatchBody":
        if (self.match_format is None) == (self.scoring_format is None):
            raise ValueError("Exactly one of match_format or scoring_format must be provided.")
        return self


class AddParticipantBody(BaseModel):
    """Body para añadir un amigo como participante."""

    friend_user_id: UUID
    team: str | None = Field(None, pattern="^(A|B)$")
    tee_category: str | None = Field(None, pattern=TEE_CATEGORY_PATTERN)
    tee_gender: str | None = Field(None, pattern=TEE_GENDER_PATTERN)


class AddGuestParticipantBody(BaseModel):
    """Body para añadir a mano un jugador invitado (sin cuenta)."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    handicap: float | None = Field(None, ge=-10.0, le=54.0)
    team: str | None = Field(None, pattern="^(A|B)$")
    tee_category: str | None = Field(None, pattern=TEE_CATEGORY_PATTERN)
    tee_gender: str | None = Field(None, pattern=TEE_GENDER_PATTERN)


class StartQuickMatchBody(BaseModel):
    """Body para iniciar la partida, indicando quien va a anotar (1 a 4)."""

    scorer_ids: list[UUID] = Field(..., min_length=1, max_length=MAX_SCORERS)

    @field_validator("scorer_ids")
    @classmethod
    def _unique_scorer_ids(cls, v: list[UUID]) -> list[UUID]:
        if len(set(v)) != len(v):
            raise ValueError("scorer_ids must not contain duplicates.")
        return v


class SubmitHoleScoreBody(BaseModel):
    """Body para registrar el score propio de un hoyo."""

    score: int = Field(..., ge=1, le=15)


# ======================================================================================
# ENDPOINTS
# ======================================================================================


@router.post(
    "/quick-matches",
    response_model=QuickMatchResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create quick match",
    description="Creates a quick match with the current user as creator/first participant.",
)
@limiter.limit("20/hour")
async def create_quick_match(
    request: Request,  # noqa: ARG001 - Required by SlowAPI for rate limiting
    body: CreateQuickMatchBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CreateQuickMatchUseCase = Depends(get_create_quick_match_use_case),
):
    try:
        request_dto = CreateQuickMatchRequestDTO(
            creator_id=current_user.id,
            golf_course_id=body.golf_course_id,
            match_format=body.match_format,
            scoring_format=body.scoring_format,
            name=body.name,
            allowance_percentage=body.allowance_percentage,
            creator_tee_category=body.creator_tee_category,
            creator_tee_gender=body.creator_tee_gender,
        )
        return await use_case.execute(request_dto)

    except GolfCourseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except GolfCourseNotApprovedError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except InvalidAllowanceViolation as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except InvalidTeeSelectionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.post(
    "/quick-matches/{quick_match_id}/participants",
    response_model=QuickMatchResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Add friend to quick match",
    description="Creator adds an accepted friend directly, without an invitation step.",
)
async def add_participant(
    quick_match_id: UUID,
    body: AddParticipantBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: AddFriendToQuickMatchUseCase = Depends(get_add_friend_to_quick_match_use_case),
):
    try:
        request_dto = AddParticipantRequestDTO(
            quick_match_id=quick_match_id,
            requester_id=current_user.id,
            friend_user_id=body.friend_user_id,
            team=body.team,
            tee_category=body.tee_category,
            tee_gender=body.tee_gender,
        )
        return await use_case.execute(request_dto)

    except QuickMatchNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except FriendUserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotQuickMatchCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except NotFriendsError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except DuplicateParticipantViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except (QuickMatchFullViolation, InvalidTeamAssignmentViolation) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except InvalidQuickMatchStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InvalidTeeSelectionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.post(
    "/quick-matches/{quick_match_id}/participants/guest",
    response_model=QuickMatchResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Add guest to quick match",
    description=(
        "Creator adds a guest player (no account) by entering their name and handicap. "
        "Their scores will be recorded by an assigned scorer once the match starts."
    ),
)
async def add_guest_participant(
    quick_match_id: UUID,
    body: AddGuestParticipantBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: AddGuestToQuickMatchUseCase = Depends(get_add_guest_to_quick_match_use_case),
):
    try:
        request_dto = AddGuestParticipantRequestDTO(
            quick_match_id=quick_match_id,
            requester_id=current_user.id,
            first_name=body.first_name,
            last_name=body.last_name,
            handicap=body.handicap,
            team=body.team,
            tee_category=body.tee_category,
            tee_gender=body.tee_gender,
        )
        return await use_case.execute(request_dto)

    except QuickMatchNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotQuickMatchCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except DuplicateParticipantViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except (QuickMatchFullViolation, InvalidTeamAssignmentViolation) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except InvalidQuickMatchStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InvalidTeeSelectionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.delete(
    "/quick-matches/{quick_match_id}/participants/{target_participant_id}",
    response_model=QuickMatchResponseDTO,
    summary="Remove participant",
    description="Removes a participant (self-leave for registered players, or creator kick).",
)
async def remove_participant(
    quick_match_id: UUID,
    target_participant_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: RemoveParticipantUseCase = Depends(get_remove_quick_match_participant_use_case),
):
    try:
        request_dto = RemoveParticipantRequestDTO(
            quick_match_id=quick_match_id,
            requester_id=current_user.id,
            target_participant_id=target_participant_id,
        )
        return await use_case.execute(request_dto)

    except QuickMatchNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotAuthorizedToRemoveError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except CreatorCannotBeRemovedViolation as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except NotQuickMatchParticipantViolation as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except InvalidQuickMatchStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post(
    "/quick-matches/{quick_match_id}/start",
    response_model=QuickMatchResponseDTO,
    summary="Start quick match",
    description=(
        "Creator starts the quick match once the roster is complete, choosing between "
        "1 and 4 registered participants (always including the creator) as scorers."
    ),
)
async def start_quick_match(
    quick_match_id: UUID,
    body: StartQuickMatchBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: StartQuickMatchUseCase = Depends(get_start_quick_match_use_case),
):
    try:
        request_dto = StartQuickMatchRequestDTO(
            quick_match_id=quick_match_id,
            requester_id=current_user.id,
            scorer_ids=body.scorer_ids,
        )
        return await use_case.execute(request_dto)

    except QuickMatchNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotQuickMatchCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except IncompleteRosterViolation as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except InvalidScorerConfigurationViolation as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except InvalidQuickMatchStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post(
    "/quick-matches/{quick_match_id}/complete",
    response_model=QuickMatchResponseDTO,
    summary="Complete quick match",
    description="Creator marks the quick match as completed.",
)
async def complete_quick_match(
    quick_match_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CompleteQuickMatchUseCase = Depends(get_complete_quick_match_use_case),
):
    try:
        return await use_case.execute(str(quick_match_id), str(current_user.id))

    except QuickMatchNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotQuickMatchCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except InvalidQuickMatchStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post(
    "/quick-matches/{quick_match_id}/cancel",
    response_model=QuickMatchResponseDTO,
    summary="Cancel quick match",
    description="Creator cancels the quick match.",
)
async def cancel_quick_match(
    quick_match_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: CancelQuickMatchUseCase = Depends(get_cancel_quick_match_use_case),
):
    try:
        return await use_case.execute(str(quick_match_id), str(current_user.id))

    except QuickMatchNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotQuickMatchCreatorError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except InvalidQuickMatchStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post(
    "/quick-matches/{quick_match_id}/holes/{hole_number}/score",
    response_model=HoleScoreResponseDTO,
    summary="Submit own hole score",
    description="Registers/updates the current user's own score for a hole. Scorers only.",
)
async def submit_hole_score(
    quick_match_id: UUID,
    hole_number: Annotated[int, Path(ge=1, le=18)],
    body: SubmitHoleScoreBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SubmitQuickMatchHoleScoreUseCase = Depends(get_submit_quick_match_hole_score_use_case),
):
    try:
        request_dto = SubmitHoleScoreRequestDTO(
            quick_match_id=quick_match_id,
            player_user_id=current_user.id,
            hole_number=hole_number,
            score=body.score,
        )
        return await use_case.execute(request_dto)

    except QuickMatchNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotQuickMatchParticipantError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except NotAScorerError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except InvalidQuickMatchStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InvalidHoleScoreViolation as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/quick-matches/{quick_match_id}/participants/{target_participant_id}/holes/{hole_number}/score",
    response_model=HoleScoreResponseDTO,
    summary="Submit hole score by proxy",
    description=(
        "Records a hole score on behalf of another participant (guest, or registered "
        "player not selected as a scorer). Only the scorer assigned to that "
        "participant may do this."
    ),
)
async def submit_proxy_hole_score(
    quick_match_id: UUID,
    target_participant_id: UUID,
    hole_number: Annotated[int, Path(ge=1, le=18)],
    body: SubmitHoleScoreBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SubmitProxyHoleScoreUseCase = Depends(
        get_submit_quick_match_proxy_hole_score_use_case
    ),
):
    try:
        request_dto = SubmitProxyHoleScoreRequestDTO(
            quick_match_id=quick_match_id,
            scorer_user_id=current_user.id,
            target_participant_id=target_participant_id,
            hole_number=hole_number,
            score=body.score,
        )
        return await use_case.execute(request_dto)

    except QuickMatchNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except TargetParticipantNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotAScorerError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except NotAssignedScorerViolation as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except InvalidQuickMatchStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InvalidHoleScoreViolation as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/quick-matches/me",
    response_model=PaginatedQuickMatchResponseDTO,
    summary="List my quick matches",
    description="Lists quick matches the current user participates in.",
)
async def list_my_quick_matches(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListMyQuickMatchesUseCase = Depends(get_list_my_quick_matches_use_case),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    return await use_case.execute(
        str(current_user.id), status_filter=status_filter, page=page, limit=limit
    )


@router.get(
    "/quick-matches/{quick_match_id}",
    response_model=QuickMatchDetailResponseDTO,
    summary="Get quick match detail",
    description=(
        "Returns quick match detail, hole scores, computed match standing, and the "
        "scorer coverage assignments (who records for whom)."
    ),
)
async def get_quick_match(
    quick_match_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetQuickMatchUseCase = Depends(get_get_quick_match_use_case),
):
    try:
        return await use_case.execute(str(quick_match_id), str(current_user.id))

    except QuickMatchNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotQuickMatchParticipantError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
