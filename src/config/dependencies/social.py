"""
Proveedores del módulo social: amistades, actividad, logros, fotos.
"""

from fastapi import Depends

from src.config.dependencies.comun import (
    get_competition_uow,
    get_get_player_stats_use_case,
    get_golf_course_uow,
    get_image_processor,
    get_quick_match_uow,
    get_social_email_service,
    get_social_uow,
    get_uow,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.social.application.ports.invitation_availability_interface import (
    InvitationAvailabilityInterface,
)
from src.modules.social.application.ports.quick_match_trash_interface import (
    QuickMatchTrashInterface,
)
from src.modules.social.application.ports.shared_games_interface import (
    SharedGamesInterface,
)
from src.modules.social.application.ports.social_email_service_interface import (
    ISocialEmailService,
)
from src.modules.social.application.ports.tournament_visibility_interface import (
    TournamentVisibilityInterface,
)
from src.modules.social.application.use_cases.block_user_use_case import BlockUserUseCase
from src.modules.social.application.use_cases.delete_profile_photo_use_case import (
    DeleteProfilePhotoUseCase,
)
from src.modules.social.application.use_cases.get_feed_unseen_count_use_case import (
    GetFeedUnseenCountUseCase,
)
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
)
from src.modules.social.application.use_cases.get_games_together_use_case import (
    GetGamesTogetherUseCase,
)
from src.modules.social.application.use_cases.get_player_activity_use_case import (
    GetPlayerActivityUseCase,
)
from src.modules.social.application.use_cases.get_player_profile_use_case import (
    GetPlayerProfileUseCase,
)
from src.modules.social.application.use_cases.get_profile_gallery_use_case import (
    GetProfileGalleryUseCase,
)
from src.modules.social.application.use_cases.get_profile_photo_image_use_case import (
    GetProfilePhotoImageUseCase,
)
from src.modules.social.application.use_cases.list_friends_use_case import ListFriendsUseCase
from src.modules.social.application.use_cases.list_pending_requests_use_case import (
    ListPendingRequestsUseCase,
)
from src.modules.social.application.use_cases.mark_feed_as_seen_use_case import (
    MarkFeedAsSeenUseCase,
)
from src.modules.social.application.use_cases.remove_friend_use_case import RemoveFriendUseCase
from src.modules.social.application.use_cases.respond_friend_request_use_case import (
    RespondFriendRequestUseCase,
)
from src.modules.social.application.use_cases.send_friend_request_use_case import (
    SendFriendRequestUseCase,
)
from src.modules.social.application.use_cases.set_activity_sharing_use_case import (
    SetActivitySharingUseCase,
)
from src.modules.social.application.use_cases.upload_profile_photo_use_case import (
    UploadProfilePhotoUseCase,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.infrastructure.adapters.invitation_availability_adapter import (
    InvitationAvailabilityAdapter,
)
from src.modules.social.infrastructure.adapters.quick_match_trash_adapter import (
    QuickMatchTrashAdapter,
)
from src.modules.social.infrastructure.adapters.shared_games_adapter import (
    SharedGamesAdapter,
)
from src.modules.social.infrastructure.adapters.tournament_visibility_adapter import (
    TournamentVisibilityAdapter,
)
from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)


def get_send_friend_request_use_case(
    uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: ISocialEmailService = Depends(get_social_email_service),
) -> SendFriendRequestUseCase:
    """Proveedor del caso de uso SendFriendRequestUseCase."""
    return SendFriendRequestUseCase(uow, user_uow, email_service)


def get_respond_friend_request_use_case(
    uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RespondFriendRequestUseCase:
    """Proveedor del caso de uso RespondFriendRequestUseCase."""
    return RespondFriendRequestUseCase(uow, user_uow)


def get_remove_friend_use_case(
    uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
) -> RemoveFriendUseCase:
    """Proveedor del caso de uso RemoveFriendUseCase."""
    return RemoveFriendUseCase(uow)


def get_block_user_use_case(
    uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> BlockUserUseCase:
    """Proveedor del caso de uso BlockUserUseCase."""
    return BlockUserUseCase(uow, user_uow)


def get_list_friends_use_case(
    uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListFriendsUseCase:
    """Proveedor del caso de uso ListFriendsUseCase."""
    return ListFriendsUseCase(uow, user_uow)


def get_list_pending_requests_use_case(
    uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListPendingRequestsUseCase:
    """Proveedor del caso de uso ListPendingRequestsUseCase."""
    return ListPendingRequestsUseCase(uow, user_uow)


def get_upload_profile_photo_use_case(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    image_processor: IImageProcessor = Depends(get_image_processor),
) -> UploadProfilePhotoUseCase:
    """Proveedor del caso de uso UploadProfilePhotoUseCase."""
    return UploadProfilePhotoUseCase(social_uow, user_uow, image_processor)


def get_profile_gallery_use_case(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> GetProfileGalleryUseCase:
    """Proveedor del caso de uso GetProfileGalleryUseCase."""
    return GetProfileGalleryUseCase(social_uow, user_uow)


def get_profile_photo_image_use_case(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
) -> GetProfilePhotoImageUseCase:
    """Proveedor del caso de uso GetProfilePhotoImageUseCase."""
    return GetProfilePhotoImageUseCase(social_uow)


def get_delete_profile_photo_use_case(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
) -> DeleteProfilePhotoUseCase:
    """Proveedor del caso de uso DeleteProfilePhotoUseCase."""
    return DeleteProfilePhotoUseCase(social_uow)


def get_shared_games(
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> SharedGamesInterface:
    """Proveedor del puerto de las partidas jugadas juntos (BE-3)."""
    return SharedGamesAdapter(quick_match_uow, competition_uow, golf_course_uow, user_uow)


def get_player_profile_use_case(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    stats_use_case: GetPlayerStatsUseCase = Depends(get_get_player_stats_use_case),
    shared_games: SharedGamesInterface = Depends(get_shared_games),
) -> GetPlayerProfileUseCase:
    """Proveedor del caso de uso GetPlayerProfileUseCase."""
    return GetPlayerProfileUseCase(social_uow, user_uow, stats_use_case, shared_games)


def get_games_together_use_case(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    shared_games: SharedGamesInterface = Depends(get_shared_games),
) -> GetGamesTogetherUseCase:
    """Proveedor del caso de uso GetGamesTogetherUseCase."""
    return GetGamesTogetherUseCase(social_uow, user_uow, shared_games)


def get_tournament_visibility(
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> TournamentVisibilityInterface:
    """Proveedor del puerto de visibilidad de torneos del feed (tabla del 22 oct, E)."""
    return TournamentVisibilityAdapter(competition_uow)


def get_invitation_availability(
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> InvitationAvailabilityInterface:
    """Proveedor del puerto de invitaciones abiertas del feed (revision final, 22 oct)."""
    return InvitationAvailabilityAdapter(competition_uow)


def get_quick_match_trash(
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
) -> QuickMatchTrashInterface:
    """Proveedor del puerto de la papelera de partidas rapidas del feed (22 oct)."""
    return QuickMatchTrashAdapter(quick_match_uow)


def get_player_activity_use_case(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    tournaments: TournamentVisibilityInterface = Depends(get_tournament_visibility),
    invitations: InvitationAvailabilityInterface = Depends(get_invitation_availability),
    quick_match_trash: QuickMatchTrashInterface = Depends(get_quick_match_trash),
) -> GetPlayerActivityUseCase:
    """Proveedor del caso de uso GetPlayerActivityUseCase."""
    return GetPlayerActivityUseCase(
        social_uow,
        user_uow,
        golf_course_uow,
        tournaments=tournaments,
        invitations=invitations,
        quick_match_trash=quick_match_trash,
    )


def get_friends_feed_use_case(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    tournaments: TournamentVisibilityInterface = Depends(get_tournament_visibility),
    invitations: InvitationAvailabilityInterface = Depends(get_invitation_availability),
    quick_match_trash: QuickMatchTrashInterface = Depends(get_quick_match_trash),
) -> GetFriendsFeedUseCase:
    """Proveedor del caso de uso GetFriendsFeedUseCase."""
    return GetFriendsFeedUseCase(
        social_uow,
        user_uow,
        golf_course_uow,
        tournaments=tournaments,
        invitations=invitations,
        quick_match_trash=quick_match_trash,
    )


def get_feed_unseen_count_use_case(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> GetFeedUnseenCountUseCase:
    """Proveedor del caso de uso GetFeedUnseenCountUseCase."""
    return GetFeedUnseenCountUseCase(social_uow, user_uow)


def get_mark_feed_as_seen_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> MarkFeedAsSeenUseCase:
    """Proveedor del caso de uso MarkFeedAsSeenUseCase."""
    return MarkFeedAsSeenUseCase(user_uow)


def get_set_activity_sharing_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
) -> SetActivitySharingUseCase:
    """Proveedor del caso de uso SetActivitySharingUseCase."""
    return SetActivitySharingUseCase(user_uow, social_uow)
