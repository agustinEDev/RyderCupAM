"""
Proveedores de la partida rápida.
"""

from fastapi import Depends

from src.config.dependencies.comun import (
    get_golf_course_uow,
    get_match_play_scoring,
    get_publish_quick_match_result_use_case,
    get_publish_round_achievements_use_case,
    get_quick_match_uow,
    get_social_uow,
    get_uow,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.quick_match.application.ports.round_achievements_publisher_interface import (
    RoundAchievementsPublisherInterface,
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
from src.modules.quick_match.application.use_cases.create_and_start_quick_match_use_case import (
    CreateAndStartQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.create_quick_match_use_case import (
    CreateQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.exclude_quick_match_from_stats_use_case import (
    ExcludeQuickMatchFromStatsUseCase,
)
from src.modules.quick_match.application.use_cases.get_quick_match_use_case import (
    GetQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.get_shared_quick_match_use_case import (
    GetSharedQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.hide_quick_match_use_case import (
    HideQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.include_quick_match_in_stats_use_case import (
    IncludeQuickMatchInStatsUseCase,
)
from src.modules.quick_match.application.use_cases.list_my_quick_matches_use_case import (
    ListMyQuickMatchesUseCase,
)
from src.modules.quick_match.application.use_cases.remove_participant_use_case import (
    RemoveParticipantUseCase,
)
from src.modules.quick_match.application.use_cases.set_participant_handicap_use_case import (
    SetParticipantHandicapUseCase,
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
from src.modules.quick_match.application.use_cases.unhide_quick_match_use_case import (
    UnhideQuickMatchUseCase,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.services.scoring_coverage_service import (
    ScoringCoverageService,
)
from src.modules.social.application.use_cases.publish_quick_match_result_use_case import (
    PublishQuickMatchResultUseCase,
)
from src.modules.social.application.use_cases.publish_round_achievements_use_case import (
    PublishRoundAchievementsUseCase,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.infrastructure.adapters.quick_match_achievements_publisher import (
    QuickMatchAchievementsPublisher,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.shared.domain.services.match_play_scoring import MatchPlayScoring


def get_create_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> CreateQuickMatchUseCase:
    """Proveedor del caso de uso CreateQuickMatchUseCase."""
    return CreateQuickMatchUseCase(uow, golf_course_uow, user_uow)


def get_create_and_start_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> CreateAndStartQuickMatchUseCase:
    """Proveedor del caso de uso CreateAndStartQuickMatchUseCase (FE #848)."""
    return CreateAndStartQuickMatchUseCase(uow, golf_course_uow, social_uow, user_uow)


def get_add_friend_to_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> AddFriendToQuickMatchUseCase:
    """Proveedor del caso de uso AddFriendToQuickMatchUseCase."""
    return AddFriendToQuickMatchUseCase(uow, social_uow, user_uow, golf_course_uow)


def get_add_guest_to_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> AddGuestToQuickMatchUseCase:
    """Proveedor del caso de uso AddGuestToQuickMatchUseCase."""
    return AddGuestToQuickMatchUseCase(uow, user_uow, golf_course_uow)


def get_remove_quick_match_participant_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RemoveParticipantUseCase:
    """Proveedor del caso de uso RemoveParticipantUseCase."""
    return RemoveParticipantUseCase(uow, user_uow)


def get_hide_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> HideQuickMatchUseCase:
    """Proveedor del caso de uso HideQuickMatchUseCase."""
    return HideQuickMatchUseCase(uow, user_uow)


def get_unhide_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UnhideQuickMatchUseCase:
    """Proveedor del caso de uso UnhideQuickMatchUseCase."""
    return UnhideQuickMatchUseCase(uow, user_uow)


def get_exclude_quick_match_from_stats_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ExcludeQuickMatchFromStatsUseCase:
    """Proveedor del caso de uso ExcludeQuickMatchFromStatsUseCase."""
    return ExcludeQuickMatchFromStatsUseCase(uow, user_uow)


def get_include_quick_match_in_stats_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> IncludeQuickMatchInStatsUseCase:
    """Proveedor del caso de uso IncludeQuickMatchInStatsUseCase."""
    return IncludeQuickMatchInStatsUseCase(uow, user_uow)


def get_set_quick_match_participant_handicap_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> SetParticipantHandicapUseCase:
    """Proveedor del caso de uso SetParticipantHandicapUseCase."""
    return SetParticipantHandicapUseCase(uow, user_uow)


def get_start_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> StartQuickMatchUseCase:
    """Proveedor del caso de uso StartQuickMatchUseCase."""
    return StartQuickMatchUseCase(uow, user_uow)


def get_round_achievements_publisher(
    publish_use_case: PublishRoundAchievementsUseCase = Depends(
        get_publish_round_achievements_use_case
    ),
    result_use_case: PublishQuickMatchResultUseCase = Depends(
        get_publish_quick_match_result_use_case
    ),
) -> RoundAchievementsPublisherInterface:
    """Proveedor del adaptador que conecta quick_match con el feed social."""
    return QuickMatchAchievementsPublisher(publish_use_case, result_use_case)


def get_complete_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    achievements: RoundAchievementsPublisherInterface = Depends(get_round_achievements_publisher),
) -> CompleteQuickMatchUseCase:
    """Proveedor del caso de uso CompleteQuickMatchUseCase."""
    return CompleteQuickMatchUseCase(uow, user_uow, achievements)


def get_cancel_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> CancelQuickMatchUseCase:
    """Proveedor del caso de uso CancelQuickMatchUseCase."""
    return CancelQuickMatchUseCase(uow, user_uow)


def get_submit_quick_match_hole_score_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
) -> SubmitQuickMatchHoleScoreUseCase:
    """Proveedor del caso de uso SubmitQuickMatchHoleScoreUseCase."""
    return SubmitQuickMatchHoleScoreUseCase(uow)


def get_scoring_coverage_service() -> ScoringCoverageService:
    """Proveedor del servicio de dominio ScoringCoverageService."""
    return ScoringCoverageService()


def get_submit_quick_match_proxy_hole_score_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    coverage_service: ScoringCoverageService = Depends(get_scoring_coverage_service),
) -> SubmitProxyHoleScoreUseCase:
    """Proveedor del caso de uso SubmitProxyHoleScoreUseCase."""
    return SubmitProxyHoleScoreUseCase(uow, coverage_service)


def get_get_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: MatchPlayScoring = Depends(get_match_play_scoring),
    coverage_service: ScoringCoverageService = Depends(get_scoring_coverage_service),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetQuickMatchUseCase:
    """Proveedor del caso de uso GetQuickMatchUseCase."""
    return GetQuickMatchUseCase(uow, user_uow, scoring_service, coverage_service, golf_course_uow)


def get_get_shared_quick_match_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    scoring_service: MatchPlayScoring = Depends(get_match_play_scoring),
    coverage_service: ScoringCoverageService = Depends(get_scoring_coverage_service),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetSharedQuickMatchUseCase:
    """Proveedor de la partida rapida de un amigo en solo lectura (bloque K)."""
    return GetSharedQuickMatchUseCase(
        uow, user_uow, social_uow, scoring_service, coverage_service, golf_course_uow
    )


def get_list_my_quick_matches_use_case(
    uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListMyQuickMatchesUseCase:
    """Proveedor del caso de uso ListMyQuickMatchesUseCase."""
    return ListMyQuickMatchesUseCase(uow, user_uow)
