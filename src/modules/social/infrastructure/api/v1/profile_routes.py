"""
Profile & Feed Routes - API REST Layer (Infrastructure).

Perfiles de jugador y feed de actividad entre amigos (BE #176).
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.config.dependencies import (
    get_current_user,
    get_friends_feed_use_case,
    get_mark_feed_as_seen_use_case,
    get_player_activity_use_case,
    get_player_profile_use_case,
)
from src.modules.social.application.dto.profile_dto import (
    FeedResponseDTO,
    PlayerProfileResponseDTO,
)
from src.modules.social.application.exceptions import ProfileNotVisibleError
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    GetFriendsFeedUseCase,
)
from src.modules.social.application.use_cases.get_player_activity_use_case import (
    GetPlayerActivityUseCase,
)
from src.modules.social.application.use_cases.get_player_profile_use_case import (
    GetPlayerProfileUseCase,
)
from src.modules.social.application.use_cases.mark_feed_as_seen_use_case import (
    MarkFeedAsSeenUseCase,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO

logger = logging.getLogger(__name__)
router = APIRouter()

# Un perfil que no se puede ver responde 404, nunca 403: un 403 diria "existe
# pero no puedes verlo", y probar identificadores serviria para averiguar que
# cuentas hay. Es la misma respuesta que para una cuenta inexistente.
PROFILE_NOT_FOUND = "Profile not found"


@router.get(
    "/users/{user_id}/profile",
    response_model=PlayerProfileResponseDTO,
    summary="Get a player's profile",
    description=(
        "The profile of a player you are friends with, including their performance "
        "summary. Returns 404 when there is no accepted friendship — deliberately "
        "indistinguishable from a profile that does not exist."
    ),
)
async def get_player_profile(
    user_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetPlayerProfileUseCase = Depends(get_player_profile_use_case),
):
    try:
        return await use_case.execute(str(current_user.id), str(user_id))
    except ProfileNotVisibleError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=PROFILE_NOT_FOUND
        ) from e


@router.get(
    "/users/{user_id}/activity",
    response_model=FeedResponseDTO,
    summary="Get a player's published achievements",
    description=(
        "The achievements a friend has published, newest first. Returns 404 under the "
        "same rule as the profile. An empty list means they publish nothing, which is "
        "not an error."
    ),
)
async def get_player_activity(
    user_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetPlayerActivityUseCase = Depends(get_player_activity_use_case),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(None, description="From a previous response's next_cursor"),
):
    try:
        return await use_case.execute(
            str(current_user.id), str(user_id), limit=limit, cursor=cursor
        )
    except ProfileNotVisibleError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=PROFILE_NOT_FOUND
        ) from e


@router.get(
    "/users/me/feed",
    response_model=FeedResponseDTO,
    summary="Get my friends' activity feed",
    description=(
        "What your friends have achieved, newest first, paginated by cursor rather than "
        "page number — the feed grows from the top, so an offset would repeat entries."
    ),
)
async def get_my_feed(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetFriendsFeedUseCase = Depends(get_friends_feed_use_case),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(None, description="From a previous response's next_cursor"),
):
    return await use_case.execute(str(current_user.id), limit=limit, cursor=cursor)


@router.put(
    "/users/me/feed/seen",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark the feed as seen",
    description=(
        "Clears the unseen counter. Separate from reading the feed on purpose: clients "
        "also fetch the feed to refresh in the background, and that should not clear it."
    ),
)
async def mark_feed_as_seen(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: MarkFeedAsSeenUseCase = Depends(get_mark_feed_as_seen_use_case),
):
    await use_case.execute(str(current_user.id))
