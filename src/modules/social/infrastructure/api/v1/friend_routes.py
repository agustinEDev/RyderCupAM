"""
Friend Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para gestion de amistades siguiendo Clean Architecture.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from src.config.dependencies import (
    get_block_user_use_case,
    get_current_user,
    get_list_friends_use_case,
    get_list_pending_requests_use_case,
    get_remove_friend_use_case,
    get_respond_friend_request_use_case,
    get_send_friend_request_use_case,
)
from src.config.rate_limit import limiter
from src.modules.social.application.dto.friendship_dto import (
    FriendshipResponseDTO,
    PaginatedFriendshipResponseDTO,
    RespondFriendRequestRequestDTO,
    SendFriendRequestRequestDTO,
)
from src.modules.social.application.exceptions import (
    AddresseeNotFoundError,
    FriendshipNotFoundError,
    NotAddresseeError,
    NotFriendshipParticipantError,
)
from src.modules.social.application.use_cases.block_user_use_case import BlockUserUseCase
from src.modules.social.application.use_cases.list_friends_use_case import ListFriendsUseCase
from src.modules.social.application.use_cases.list_pending_requests_use_case import (
    ListPendingRequestsUseCase,
)
from src.modules.social.application.use_cases.remove_friend_use_case import RemoveFriendUseCase
from src.modules.social.application.use_cases.respond_friend_request_use_case import (
    RespondFriendRequestUseCase,
)
from src.modules.social.application.use_cases.send_friend_request_use_case import (
    SendFriendRequestUseCase,
)
from src.modules.social.domain.exceptions.social_violations import (
    BlockedUserViolation,
    DuplicateFriendRequestViolation,
    InvalidFriendshipStatusViolation,
    SelfFriendRequestViolation,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO

logger = logging.getLogger(__name__)
router = APIRouter()


# ======================================================================================
# REQUEST BODY MODELS (Presentation Layer)
# ======================================================================================


class SendFriendRequestBody(BaseModel):
    """Body para enviar una solicitud de amistad."""

    addressee_id: UUID


class RespondFriendRequestBody(BaseModel):
    """Body para responder a una solicitud de amistad."""

    action: str = Field(
        ..., description="Action to perform: ACCEPT or DECLINE", pattern="^(ACCEPT|DECLINE)$"
    )


# ======================================================================================
# ENDPOINTS
# ======================================================================================


@router.post(
    "/friends/requests",
    response_model=FriendshipResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Send friend request",
    description="Sends a friend request to another user. Rate limited to 20 per hour.",
)
@limiter.limit("20/hour")
async def send_friend_request(
    request: Request,  # noqa: ARG001 - Required by SlowAPI for rate limiting
    body: SendFriendRequestBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SendFriendRequestUseCase = Depends(get_send_friend_request_use_case),
):
    try:
        request_dto = SendFriendRequestRequestDTO(
            requester_id=current_user.id,
            addressee_id=body.addressee_id,
        )
        return await use_case.execute(request_dto)

    except AddresseeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SelfFriendRequestViolation as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except BlockedUserViolation as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except DuplicateFriendRequestViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.post(
    "/friends/requests/{friendship_id}/respond",
    response_model=FriendshipResponseDTO,
    summary="Respond to friend request",
    description="Accept or decline a friend request.",
)
async def respond_to_friend_request(
    friendship_id: UUID,
    body: RespondFriendRequestBody,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: RespondFriendRequestUseCase = Depends(get_respond_friend_request_use_case),
):
    try:
        request_dto = RespondFriendRequestRequestDTO(
            friendship_id=friendship_id,
            user_id=current_user.id,
            action=body.action,
        )
        return await use_case.execute(request_dto)

    except FriendshipNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotAddresseeError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except InvalidFriendshipStatusViolation as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.delete(
    "/friends/{friendship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove friendship",
    description="Removes a friendship, cancels a pending request, or unblocks a user.",
)
async def remove_friend(
    friendship_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: RemoveFriendUseCase = Depends(get_remove_friend_use_case),
):
    try:
        await use_case.execute(str(friendship_id), str(current_user.id))

    except FriendshipNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except NotFriendshipParticipantError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.post(
    "/friends/{user_id}/block",
    response_model=FriendshipResponseDTO,
    summary="Block user",
    description="Blocks another user, removing any existing friendship or pending request.",
)
async def block_user(
    user_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: BlockUserUseCase = Depends(get_block_user_use_case),
):
    try:
        return await use_case.execute(str(current_user.id), str(user_id))

    except AddresseeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except SelfFriendRequestViolation as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/friends/me",
    response_model=PaginatedFriendshipResponseDTO,
    summary="List my friends",
    description="List accepted friends of the authenticated user.",
)
async def list_my_friends(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListFriendsUseCase = Depends(get_list_friends_use_case),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    return await use_case.execute(str(current_user.id), page=page, limit=limit)


@router.get(
    "/friends/requests/me",
    response_model=PaginatedFriendshipResponseDTO,
    summary="List my pending friend requests",
    description="List pending friend requests received or sent by the authenticated user.",
)
async def list_my_pending_requests(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListPendingRequestsUseCase = Depends(get_list_pending_requests_use_case),
    direction: str = Query("received", pattern="^(received|sent)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    return await use_case.execute(str(current_user.id), direction=direction, page=page, limit=limit)
