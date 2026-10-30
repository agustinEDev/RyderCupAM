import logging
import os
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.database import async_session_maker
from src.config.refresco_de_handicaps import LanzadorEnSegundoPlano, refresco_activado
from src.config.settings import settings
from src.config.terms_guard import require_current_terms
from src.modules.competition.application.ports.amigos_interface import AmigosInterface
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CompetitionActivityPublisherInterface,
)
from src.modules.competition.application.ports.eventos_de_amigos_interface import (
    EventosDeAmigosInterface,
)
from src.modules.competition.application.ports.invitation_email_service_interface import (
    IInvitationEmailService,
)
from src.modules.competition.application.ports.lanzador_de_actualizaciones import (
    LanzadorDeActualizaciones,
)
from src.modules.competition.application.ports.tournament_achievements_publisher_interface import (
    TournamentAchievementsPublisherInterface,
)
from src.modules.competition.application.services.envelope_desk import EnvelopeDesk
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
)
from src.modules.competition.application.use_cases.activate_competition_use_case import (
    ActivateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.actualizar_handicaps_use_case import (
    ActualizarHandicapsUseCase,
    VentanaDeActualizacionUseCase,
)
from src.modules.competition.application.use_cases.add_golf_course_use_case import (
    AddGolfCourseToCompetitionUseCase,
)
from src.modules.competition.application.use_cases.anotar_hoyo_de_partida_use_case import (
    AnotarHoyoDePartidaUseCase,
)
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
)
from src.modules.competition.application.use_cases.cancel_competition_use_case import (
    CancelCompetitionUseCase,
)
from src.modules.competition.application.use_cases.cancel_enrollment_use_case import (
    CancelEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.cancel_invitation_use_case import (
    CancelInvitationUseCase,
)
from src.modules.competition.application.use_cases.clasificaciones_use_case import (
    ClasificacionDeLaFranjaUseCase,
    ClasificacionGeneralUseCase,
    ClasificacionScratchUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.concede_match_use_case import (
    ConcedeMatchUseCase,
)
from src.modules.competition.application.use_cases.configure_schedule_use_case import (
    ConfigureScheduleUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.create_round_use_case import (
    CreateRoundUseCase,
)
from src.modules.competition.application.use_cases.declare_walkover_use_case import (
    DeclareWalkoverUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    DeleteCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_round_use_case import (
    DeleteRoundUseCase,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.application.use_cases.entregar_tarjeta_de_partida_use_case import (
    EntregarTarjetaDePartidaUseCase,
    RetirarseDePartidaUseCase,
)
from src.modules.competition.application.use_cases.fill_captain_use_case import (
    FillCaptainUseCase,
)
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
)
from src.modules.competition.application.use_cases.get_competition_summary_use_case import (
    GetCompetitionSummaryUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_draft_use_case import GetDraftUseCase
from src.modules.competition.application.use_cases.get_envelopes_use_case import (
    GetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.get_handicap_update_status_use_case import (
    GetHandicapUpdateStatusUseCase,
)
from src.modules.competition.application.use_cases.get_leaderboard_use_case import (
    GetLeaderboardUseCase,
)
from src.modules.competition.application.use_cases.get_match_detail_use_case import (
    GetMatchDetailUseCase,
)
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    GetScheduleUseCase,
)
from src.modules.competition.application.use_cases.get_scoring_view_use_case import (
    GetScoringViewUseCase,
)
from src.modules.competition.application.use_cases.handle_enrollment_use_case import (
    HandleEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.list_competition_invitations_use_case import (
    ListCompetitionInvitationsUseCase,
)
from src.modules.competition.application.use_cases.list_competitions_use_case import (
    ListCompetitionsUseCase,
)
from src.modules.competition.application.use_cases.list_enrollments_use_case import (
    ListEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.list_my_invitations_use_case import (
    ListMyInvitationsUseCase,
)
from src.modules.competition.application.use_cases.list_my_pending_envelopes_use_case import (
    ListMyPendingEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.list_my_sessions_without_matches_use_case import (
    ListMySessionsWithoutMatchesUseCase,
)
from src.modules.competition.application.use_cases.listas_de_espera_use_case import (
    DejarDeEsperarUseCase,
    EntendidoUseCase,
    EsperarUseCase,
    MisPlazasAsignadasUseCase,
)
from src.modules.competition.application.use_cases.make_draft_pick_use_case import (
    MakeDraftPickUseCase,
)
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.name_vice_captain_use_case import (
    NameViceCaptainUseCase,
)
from src.modules.competition.application.use_cases.organizador_de_partidas_use_case import (
    BorrarHoyoDePartidaUseCase,
    CerrarFranjaUseCase,
    CorregirHoyoDePartidaUseCase,
    MarcarNoPresentadoUseCase,
    ReabrirTarjetaUseCase,
    RetirarJugadorUseCase,
    ValidarLoAnotadoUseCase,
)
from src.modules.competition.application.use_cases.partidas_use_case import (
    BorrarPartidasUseCase,
    CambiarMarcadoresUseCase,
    GenerarPartidasUseCase,
    MisPartidasUseCase,
    MoverJugadorUseCase,
    ReordenarPartidasUseCase,
    VerPartidasUseCase,
)
from src.modules.competition.application.use_cases.plazas_en_franjas_use_case import (
    CogerPlazaUseCase,
    SoltarPlazaUseCase,
)
from src.modules.competition.application.use_cases.programar_actualizacion_use_case import (
    AnularProgramacionUseCase,
    ProgramarActualizacionUseCase,
)
from src.modules.competition.application.use_cases.reassign_match_players_use_case import (
    ReassignMatchPlayersUseCase,
)
from src.modules.competition.application.use_cases.remove_custom_handicap_use_case import (
    RemoveCustomHandicapUseCase,
)
from src.modules.competition.application.use_cases.remove_enrolled_player_use_case import (
    RemoveEnrolledPlayerUseCase,
)
from src.modules.competition.application.use_cases.remove_golf_course_use_case import (
    RemoveGolfCourseFromCompetitionUseCase,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.reorder_golf_courses_use_case import (
    ReorderGolfCoursesUseCase,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    RequestEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.reset_envelopes_use_case import (
    ResetEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.application.use_cases.reveal_envelopes_use_case import (
    RevealEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.revert_competition_status_use_case import (
    RevertCompetitionStatusUseCase,
)
from src.modules.competition.application.use_cases.revert_competition_to_in_progress_use_case import (
    RevertCompetitionToInProgressUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_email_use_case import (
    SendInvitationByEmailUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.application.use_cases.set_custom_handicap_use_case import (
    SetCustomHandicapUseCase,
)
from src.modules.competition.application.use_cases.set_name_preference_use_case import (
    SetNamePreferenceUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    StartCompetitionUseCase,
)
from src.modules.competition.application.use_cases.start_draft_use_case import (
    StartDraftUseCase,
)
from src.modules.competition.application.use_cases.submit_envelope_use_case import (
    SubmitEnvelopeUseCase,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.application.use_cases.submit_scorecard_use_case import (
    SubmitScorecardUseCase,
)
from src.modules.competition.application.use_cases.undo_teams_use_case import (
    UndoTeamsUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    UpdateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_match_status_use_case import (
    UpdateMatchStatusUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.application.use_cases.update_stroke_play_settings_use_case import (
    UpdateStrokePlaySettingsUseCase,
)
from src.modules.competition.application.use_cases.ver_anotacion_de_partida_use_case import (
    VerAnotacionDePartidaUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.application.use_cases.withdraw_match_player_use_case import (
    WithdrawMatchPlayerUseCase,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.services.schedule_format_service import (
    ScheduleFormatService,
)
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.services.snake_draft_service import (
    SnakeDraftService,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.competition.infrastructure.services.competition_timezone_from_course import (
    CompetitionTimezoneFromCourse,
)
from src.modules.golf_course.application.ports.recent_hole_sample_senders import (
    IRecentHoleSampleSenders,
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
from src.modules.golf_course.application.use_cases.hole_map_use_cases import (
    ApproveHoleMapUseCase,
    GetApprovedHoleMapUseCase,
    GetHoleMapForReviewUseCase,
    ListPendingHoleMapsUseCase,
    RejectHoleMapUseCase,
)
from src.modules.golf_course.application.use_cases.hole_report_use_cases import (
    DiscardHoleReportUseCase,
    SubmitHoleReportUseCase,
)
from src.modules.golf_course.application.use_cases.hole_review_use_cases import (
    GetHoleReviewUseCase,
    ListHoleReviewsUseCase,
)
from src.modules.golf_course.application.use_cases.hole_sample_use_cases import (
    ListHoleSamplesUseCase,
    SubmitHoleSampleUseCase,
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
from src.modules.golf_course.application.use_cases.saved_hole_use_cases import (
    DeleteHoleSampleUseCase,
    ReopenHoleUseCase,
    SaveHoleLineUseCase,
)
from src.modules.golf_course.application.use_cases.update_golf_course_use_case import (
    UpdateGolfCourseUseCase,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.golf_course.infrastructure.services.in_memory_recent_hole_sample_senders import (
    InMemoryRecentHoleSampleSenders,
)
from src.modules.golf_course.infrastructure.services.tzfpy_timezone_resolver import (
    TzfpyTimezoneResolver,
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
from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_unit_of_work import (
    SQLAlchemyQuickMatchUnitOfWork,
)
from src.modules.social.application.ports.invitation_availability_interface import (
    InvitationAvailabilityInterface,
)
from src.modules.social.application.ports.player_course_history_interface import (
    PlayerCourseHistoryInterface,
)
from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
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
from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
)
from src.modules.social.application.use_cases.publish_quick_match_result_use_case import (
    PublishQuickMatchResultUseCase,
)
from src.modules.social.application.use_cases.publish_round_achievements_use_case import (
    PublishRoundAchievementsUseCase,
)
from src.modules.social.application.use_cases.publish_tournament_achievements_use_case import (
    PublishTournamentAchievementsUseCase,
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
from src.modules.social.infrastructure.adapters.amigos_adapter import AmigosAdapter
from src.modules.social.infrastructure.adapters.competition_activity_publisher import (
    CompetitionActivityPublisher,
)
from src.modules.social.infrastructure.adapters.eventos_de_amigos_adapter import (
    EventosDeAmigosAdapter,
)
from src.modules.social.infrastructure.adapters.invitation_availability_adapter import (
    InvitationAvailabilityAdapter,
)
from src.modules.social.infrastructure.adapters.player_course_history_adapter import (
    PlayerCourseHistoryAdapter,
)
from src.modules.social.infrastructure.adapters.player_differentials_adapter import (
    StatsPlayerDifferentialsAdapter,
)
from src.modules.social.infrastructure.adapters.quick_match_achievements_publisher import (
    QuickMatchAchievementsPublisher,
)
from src.modules.social.infrastructure.adapters.quick_match_trash_adapter import (
    QuickMatchTrashAdapter,
)
from src.modules.social.infrastructure.adapters.shared_games_adapter import (
    SharedGamesAdapter,
)
from src.modules.social.infrastructure.adapters.tournament_achievements_publisher import (
    TournamentAchievementsPublisher,
)
from src.modules.social.infrastructure.adapters.tournament_visibility_adapter import (
    TournamentVisibilityAdapter,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.social_unit_of_work import (
    SQLAlchemySocialUnitOfWork,
)
from src.modules.support.application.use_cases.submit_contact_use_case import (
    SubmitContactUseCase,
)
from src.modules.support.infrastructure.services.github_issue_service import (
    GitHubIssueService,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
from src.modules.user.application.ports.email_service_interface import IEmailService
from src.modules.user.application.ports.google_oauth_service_interface import (
    IGoogleOAuthService,
)
from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.ports.token_service_interface import ITokenService
from src.modules.user.application.use_cases.accept_terms_use_case import AcceptTermsUseCase
from src.modules.user.application.use_cases.activate_uploaded_avatar_use_case import (
    ActivateUploadedAvatarUseCase,
)
from src.modules.user.application.use_cases.admin_delete_user_use_case import (
    AdminDeleteUserUseCase,
)
from src.modules.user.application.use_cases.admin_list_users_use_case import (
    AdminListUsersUseCase,
)
from src.modules.user.application.use_cases.admin_set_user_active_use_case import (
    AdminSetUserActiveUseCase,
)
from src.modules.user.application.use_cases.admin_update_user_use_case import (
    AdminUpdateUserUseCase,
)
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.application.use_cases.get_admin_stats_use_case import (
    GetAdminStatsUseCase,
)
from src.modules.user.application.use_cases.get_avatar_image_use_case import (
    GetAvatarImageUseCase,
)
from src.modules.user.application.use_cases.get_avatar_preset_image_use_case import (
    GetAvatarPresetImageUseCase,
)
from src.modules.user.application.use_cases.get_current_user_use_case import (
    GetCurrentUserUseCase,
)
from src.modules.user.application.use_cases.get_my_avatar_upload_image_use_case import (
    GetMyAvatarUploadImageUseCase,
)
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.application.use_cases.get_recent_matches_use_case import (
    GetRecentMatchesUseCase,
)
from src.modules.user.application.use_cases.google_login_use_case import (
    GoogleLoginUseCase,
)
from src.modules.user.application.use_cases.link_google_account_use_case import (
    LinkGoogleAccountUseCase,
)
from src.modules.user.application.use_cases.list_avatar_presets_use_case import (
    ListAvatarPresetsUseCase,
)
from src.modules.user.application.use_cases.list_my_avatar_uploads_use_case import (
    ListMyAvatarUploadsUseCase,
)
from src.modules.user.application.use_cases.list_user_devices_use_case import (
    ListUserDevicesUseCase,
)
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.application.use_cases.logout_user_use_case import (
    LogoutUserUseCase,
)
from src.modules.user.application.use_cases.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.modules.user.application.use_cases.refresh_own_handicap_use_case import (
    RefreshOwnHandicapUseCase,
)
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.application.use_cases.register_user_use_case import (
    RegisterUserUseCase,
)
from src.modules.user.application.use_cases.remove_avatar_use_case import RemoveAvatarUseCase
from src.modules.user.application.use_cases.request_password_reset_use_case import (
    RequestPasswordResetUseCase,
)
from src.modules.user.application.use_cases.resend_verification_email_use_case import (
    ResendVerificationEmailUseCase,
)
from src.modules.user.application.use_cases.reset_password_use_case import (
    ResetPasswordUseCase,
)
from src.modules.user.application.use_cases.revoke_device_use_case import (
    RevokeDeviceUseCase,
)
from src.modules.user.application.use_cases.search_users_use_case import SearchUsersUseCase
from src.modules.user.application.use_cases.set_avatar_preset_use_case import (
    SetAvatarPresetUseCase,
)
from src.modules.user.application.use_cases.unlink_google_account_use_case import (
    UnlinkGoogleAccountUseCase,
)
from src.modules.user.application.use_cases.unlock_account_use_case import (
    UnlockAccountUseCase,
)
from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import (
    UpdateMultipleHandicapsUseCase,
)
from src.modules.user.application.use_cases.update_profile_use_case import (
    UpdateProfileUseCase,
)
from src.modules.user.application.use_cases.update_security_use_case import (
    UpdateSecurityUseCase,
)
from src.modules.user.application.use_cases.update_user_handicap_manually_use_case import (
    UpdateUserHandicapManuallyUseCase,
)
from src.modules.user.application.use_cases.update_user_handicap_use_case import (
    UpdateUserHandicapUseCase,
)
from src.modules.user.application.use_cases.upload_avatar_use_case import UploadAvatarUseCase
from src.modules.user.application.use_cases.validate_reset_token_use_case import (
    ValidateResetTokenUseCase,
)
from src.modules.user.application.use_cases.verify_email_use_case import (
    VerifyEmailUseCase,
)
from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.services.handicap_service import HandicapService
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.external.filesystem_avatar_preset_provider import (
    FileSystemAvatarPresetProvider,
)
from src.modules.user.infrastructure.external.google_oauth_service import (
    GoogleOAuthService,
)
from src.modules.user.infrastructure.external.pillow_image_processor import (
    PillowImageProcessor,
)
from src.modules.user.infrastructure.external.rfeg_handicap_service import (
    RFEGHandicapService,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_device_mapper import (
    user_devices_table,
)
from src.modules.user.infrastructure.security.security_audit_logger import SecurityAuditLogger
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.services.match_play_scoring import MatchPlayScoring
from src.shared.domain.services.playing_handicap_calculator import (
    PlayingHandicapCalculator,
)
from src.shared.infrastructure.email.email_service import EmailService
from src.shared.infrastructure.http.http_context_validator import get_trusted_client_ip
from src.shared.infrastructure.persistence.sqlalchemy.country_repository import (
    SQLAlchemyCountryRepository,
)
from src.shared.infrastructure.security.cookie_handler import read_access_token
from src.shared.infrastructure.security.jwt_handler import (
    JWTTokenService,
    verify_access_token,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Proveedor de sesión de base de datos para la inyección de dependencias de FastAPI.

    Esta función es un generador asíncrono que:
    1. Crea una nueva sesión de SQLAlchemy para una petición entrante.
    2. Proporciona (yields) esta sesión al endpoint.
    3. Se asegura de que la sesión se cierre siempre al final,
       liberando la conexión a la base de datos.
    """
    async with async_session_maker() as session:
        yield session


def get_uow(
    session: AsyncSession = Depends(get_db_session),
) -> UserUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para la inyección de dependencias.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `UserUnitOfWorkInterface`.
    """
    return SQLAlchemyUnitOfWork(session)


def get_handicap_service() -> HandicapService:
    """
    Proveedor del servicio de hándicap.

    Esta función:
    1. Crea una instancia de RFEGHandicapService.
    2. Configura el timeout apropiado.
    3. Devuelve la instancia que implementa HandicapService.

    Returns:
        Implementación concreta del servicio de hándicap (RFEG)
    """
    return RFEGHandicapService(timeout=10)


def get_email_service() -> IEmailService:
    """
    Proveedor del servicio de email.

    Esta función:
    1. Crea una instancia de EmailService (Mailgun).
    2. Devuelve la instancia que implementa IEmailService.

    Returns:
        Implementación concreta del servicio de email (Mailgun)
    """
    return EmailService()


def get_token_service() -> ITokenService:
    """
    Proveedor del servicio de tokens.

    Esta función:
    1. Crea una instancia de JWTTokenService.
    2. Devuelve la instancia que implementa ITokenService.

    Returns:
        Implementación concreta del servicio de tokens (JWT)
    """
    return JWTTokenService()


def get_country_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CountryRepositoryInterface:
    """
    Proveedor del repositorio de países.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyCountryRepository`.
    3. Devuelve la instancia que implementa CountryRepositoryInterface.

    Returns:
        Implementación concreta del repositorio de países (SQLAlchemy)
    """
    return SQLAlchemyCountryRepository(session)


def get_security_audit_logger() -> ISecurityAuditLogger:
    """Proveedor del puerto de auditoría de seguridad (el SecurityLogger compartido)."""
    return SecurityAuditLogger()


def get_register_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    country_repository: CountryRepositoryInterface = Depends(get_country_repository),
    handicap_service: HandicapService = Depends(get_handicap_service),
    email_service: IEmailService = Depends(get_email_service),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> RegisterUserUseCase:
    """
    Proveedor del caso de uso RegisterUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_country_repository` para validar códigos de país.
    3. Depende de `get_handicap_service` para buscar hándicaps.
    4. Depende de `get_email_service` para envío de emails de verificación.
    5. Crea una instancia de `RegisterUserUseCase` con esas dependencias.
    6. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RegisterUserUseCase(
        uow=uow,
        country_repository=country_repository,
        handicap_service=handicap_service,
        email_service=email_service,
        security_audit=security_audit,
    )


def get_find_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> FindUserUseCase:
    """
    Proveedor del caso de uso FindUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `FindUserUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return FindUserUseCase(uow)


def get_search_users_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> SearchUsersUseCase:
    """Proveedor del caso de uso SearchUsersUseCase."""
    return SearchUsersUseCase(uow=uow)


def get_update_handicap_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    handicap_service: HandicapService = Depends(get_handicap_service),
) -> UpdateUserHandicapUseCase:
    """
    Proveedor del caso de uso UpdateUserHandicapUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_handicap_service` para buscar hándicaps.
    3. Crea una instancia de `UpdateUserHandicapUseCase`.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateUserHandicapUseCase(uow, handicap_service)


def get_refresh_own_handicap_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    handicap_service: HandicapService = Depends(get_handicap_service),
) -> RefreshOwnHandicapUseCase:
    """
    Proveedor del caso de uso RefreshOwnHandicapUseCase (RyderCupAM#340).

    El refresco del hándicap que antes hacía el login, ahora aparte para que el
    login no espere a la RFEG.
    """
    return RefreshOwnHandicapUseCase(uow, handicap_service)


def get_update_multiple_handicaps_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    handicap_service: HandicapService = Depends(get_handicap_service),
) -> UpdateMultipleHandicapsUseCase:
    """
    Proveedor del caso de uso UpdateMultipleHandicapsUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_handicap_service` para buscar hándicaps.
    3. Crea una instancia de `UpdateMultipleHandicapsUseCase`.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateMultipleHandicapsUseCase(uow, handicap_service)


def get_update_handicap_manually_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UpdateUserHandicapManuallyUseCase:
    """
    Proveedor del caso de uso UpdateUserHandicapManuallyUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `UpdateUserHandicapManuallyUseCase`.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.

    Nota: Este caso de uso NO depende del HandicapService porque actualiza
    manualmente sin consultar servicios externos como RFEG.
    """
    return UpdateUserHandicapManuallyUseCase(uow)


def get_register_device_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RegisterDeviceUseCase:
    """
    Proveedor del caso de uso RegisterDeviceUseCase (v1.13.0 - Device Fingerprinting).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (user_devices repository).
    2. Crea una instancia de `RegisterDeviceUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada internamente por Login y RefreshToken.

    Note:
        Este use case NO tiene endpoint directo. Se llama internamente desde:
        - LoginUserUseCase (auto-registro en login exitoso)
        - RefreshAccessTokenUseCase (auto-registro en refresh exitoso)
    """
    return RegisterDeviceUseCase(uow)


def get_login_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service),
    register_device_use_case: RegisterDeviceUseCase = Depends(get_register_device_use_case),
) -> LoginUserUseCase:
    """
    Proveedor del caso de uso LoginUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_token_service` para generación de tokens JWT.
    3. Depende de `get_register_device_use_case` para device fingerprinting (v1.13.0).
    4. Crea una instancia de `LoginUserUseCase` con esas dependencias.
    5. Devuelve la instancia lista para ser usada por el endpoint de la API.

    Ya no recibe el servicio de hándicap: el login no espera a la RFEG
    (RyderCupAM#340); eso lo hace `get_refresh_own_handicap_use_case`.
    """
    return LoginUserUseCase(uow, token_service, register_device_use_case)


def get_logout_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> LogoutUserUseCase:
    """
    Proveedor del caso de uso LogoutUserUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `LogoutUserUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return LogoutUserUseCase(uow)


def get_refresh_access_token_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service),
    register_device_use_case: RegisterDeviceUseCase = Depends(get_register_device_use_case),
) -> RefreshAccessTokenUseCase:
    """
    Proveedor del caso de uso RefreshAccessTokenUseCase (Session Timeout - v1.8.0).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (users + refresh_tokens + user_devices).
    2. Depende de `get_token_service` para generación de tokens JWT.
    3. Depende de `get_register_device_use_case` para device fingerprinting (v1.13.0).
    4. Crea una instancia de `RefreshAccessTokenUseCase` con esas dependencias.
    5. Devuelve la instancia lista para ser usada por el endpoint /refresh-token.
    """
    return RefreshAccessTokenUseCase(uow, token_service, register_device_use_case)


def get_update_profile_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    country_repository: CountryRepositoryInterface = Depends(get_country_repository),
) -> UpdateProfileUseCase:
    """
    Proveedor del caso de uso UpdateProfileUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_country_repository` para validar códigos de país.
    3. Crea una instancia de `UpdateProfileUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateProfileUseCase(uow, country_repository)


def get_update_security_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
) -> UpdateSecurityUseCase:
    """
    Proveedor del caso de uso UpdateSecurityUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de emails de verificación.
    3. Crea una instancia de `UpdateSecurityUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateSecurityUseCase(uow, email_service)


# ============================================================================
# AVATAR (v2.3.0)
# ============================================================================


def get_image_processor() -> IImageProcessor:
    """Proveedor del procesador de imágenes (Pillow) para avatares subidos."""
    return PillowImageProcessor()


def get_avatar_preset_provider() -> IAvatarPresetProvider:
    """Proveedor del catálogo de presets de avatar (assets estáticos en disco)."""
    return FileSystemAvatarPresetProvider()


def get_set_avatar_preset_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> SetAvatarPresetUseCase:
    """Proveedor del caso de uso SetAvatarPresetUseCase."""
    return SetAvatarPresetUseCase(uow)


def get_upload_avatar_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    image_processor: IImageProcessor = Depends(get_image_processor),
) -> UploadAvatarUseCase:
    """Proveedor del caso de uso UploadAvatarUseCase."""
    return UploadAvatarUseCase(uow, image_processor)


def get_activate_uploaded_avatar_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ActivateUploadedAvatarUseCase:
    """Proveedor del caso de uso ActivateUploadedAvatarUseCase."""
    return ActivateUploadedAvatarUseCase(uow)


def get_list_my_avatar_uploads_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListMyAvatarUploadsUseCase:
    """Proveedor del caso de uso ListMyAvatarUploadsUseCase."""
    return ListMyAvatarUploadsUseCase(uow)


def get_accept_terms_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    security_audit: ISecurityAuditLogger = Depends(get_security_audit_logger),
) -> AcceptTermsUseCase:
    """Proveedor del caso de uso AcceptTermsUseCase."""
    return AcceptTermsUseCase(uow, security_audit)


def get_remove_avatar_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RemoveAvatarUseCase:
    """Proveedor del caso de uso RemoveAvatarUseCase."""
    return RemoveAvatarUseCase(uow)


def get_avatar_image_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    preset_provider: IAvatarPresetProvider = Depends(get_avatar_preset_provider),
) -> GetAvatarImageUseCase:
    """Proveedor del caso de uso GetAvatarImageUseCase."""
    return GetAvatarImageUseCase(uow, preset_provider)


def get_my_avatar_upload_image_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> GetMyAvatarUploadImageUseCase:
    """Proveedor del caso de uso GetMyAvatarUploadImageUseCase."""
    return GetMyAvatarUploadImageUseCase(uow)


def get_list_avatar_presets_use_case() -> ListAvatarPresetsUseCase:
    """Proveedor del caso de uso ListAvatarPresetsUseCase."""
    return ListAvatarPresetsUseCase()


def get_avatar_preset_image_use_case(
    preset_provider: IAvatarPresetProvider = Depends(get_avatar_preset_provider),
) -> GetAvatarPresetImageUseCase:
    """Proveedor del caso de uso GetAvatarPresetImageUseCase."""
    return GetAvatarPresetImageUseCase(preset_provider)


# Esquema de seguridad HTTP Bearer para Swagger
# IMPORTANTE: auto_error=False permite que el endpoint no falle si no hay header Authorization
# Esto es necesario para el middleware dual (cookies + headers)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: ARG001 - declara el esquema Bearer en OpenAPI; el token lo lee read_access_token
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UserResponseDTO:
    """
    Dependencia para obtener el usuario actual desde el token JWT.

    FASE TRANSITORIA (v1.8.0 - v2.0.0):
    Soporta autenticación dual para migración gradual del frontend:

    1. **httpOnly Cookie** (PRIORIDAD 1 - Recomendado):
       - Intenta leer JWT desde cookie "access_token"
       - Protección contra XSS (JavaScript no puede leerla)

    2. **Authorization Header** (PRIORIDAD 2 - LEGACY - Fallback):
       - Si no hay cookie, lee desde header "Authorization: Bearer <token>"
       - Permite compatibilidad con frontend actual (localStorage)
       - TODO (v2.0.0): Eliminar soporte para headers cuando frontend migre

    Flujo de Autenticación:
    1. Extrae token desde cookie O header (prioridad a cookie)
    2. Verifica y decodifica el token JWT
    3. Busca el usuario en la base de datos
    4. Retorna el usuario autenticado

    Security Improvements (OWASP A01/A02):
    - httpOnly cookie: JavaScript NO puede leer el token (previene XSS)
    - Fallback a headers: Compatibilidad backward sin breaking changes

    Args:
        request: Request de FastAPI (para leer cookies)
        credentials: Credenciales del header Authorization (opcional ahora)
        uow: Unit of Work para acceso a datos

    Raises:
        HTTPException 401: Si no hay token, es inválido, o el usuario no existe

    Returns:
        Usuario autenticado

    Example:
        @router.get("/protected")
        async def protected_route(current_user: UserResponseDTO = Depends(get_current_user)):
            return {"message": f"Hello {current_user.email}"}
    """
    # Cookie httpOnly primero y, si no hay, Authorization: Bearer (LEGACY). La misma
    # regla con la que el rate limit decide de quién es la petición (#273)
    token = read_access_token(request)

    # Si no hay token en ninguno de los dos lugares, rechazar autenticación
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de autenticación no proporcionadas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar y decodificar token (mismo código que antes)
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extraer user_id del payload
    user_id_str: str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: falta subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Buscar usuario
    use_case = GetCurrentUserUseCase(uow)
    user = await use_case.execute(user_id_str)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Device Fingerprinting Security Check (v1.13.0):
    # Verificar que el dispositivo actual NO esté revocado
    # Si el dispositivo fue revocado, el token es inválido aunque técnicamente sea válido
    logger = logging.getLogger(__name__)

    user_agent = request.headers.get("User-Agent", "unknown")

    # Extraer IP real del cliente (usa shared helper con soporte Cloudflare + proxies)
    ip_address = get_trusted_client_ip(
        request, settings.TRUSTED_PROXIES, settings.TRUST_CLOUDFLARE_HEADERS
    )

    if user_agent != "unknown" and ip_address:
        try:
            # Crear fingerprint del dispositivo actual
            current_fingerprint = DeviceFingerprint.create(
                user_agent=user_agent, ip_address=ip_address
            )

            # Buscar dispositivo por fingerprint (usando nueva transacción)
            # IMPORTANTE: NO usamos find_by_user_and_fingerprint porque filtra por is_active=True
            # Necesitamos encontrar el dispositivo AUNQUE esté revocado para bloquearlo
            user_id_vo = UserId(user_id_str)
            async with uow:
                # Query directo sin filtrar por is_active
                statement = (
                    select(UserDevice)
                    .where(UserDevice.user_id == user_id_vo)  # type: ignore[arg-type]
                    .where(UserDevice.fingerprint_hash == current_fingerprint.fingerprint_hash)  # type: ignore[arg-type]
                    # NO filtramos por is_active para encontrar dispositivos revocados
                    # Ordenamos por is_active DESC para que si hay múltiples, tome el activo primero
                    .order_by(user_devices_table.c.is_active.desc())
                    .limit(1)
                )
                result = await uow._session.execute(statement)
                device = result.scalar_one_or_none()

                # Si el dispositivo existe pero está revocado, denegar acceso
                if device and not device.is_active:
                    logger.warning(
                        f"Access denied: Revoked device {device.id} attempted access for user {user_id_str}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Dispositivo revocado. Por favor, inicia sesión nuevamente.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
        except HTTPException:
            # Re-lanzar HTTPException para que FastAPI la maneje
            raise
        except Exception as e:
            # Si hay error al crear fingerprint o consultar BD, continuar (no bloquear por errores técnicos)
            # Esto previene que un error en device fingerprinting bloquee a todos los usuarios
            logger.error(
                f"Error during device validation for user {user_id_str}: {type(e).__name__}: {e}"
            )
            pass

    # Términos de uso (B6): sin la versión vigente aceptada, 403
    # TERMS_NOT_ACCEPTED en toda ruta con sesión salvo las exentas
    # (src/config/terms_guard.py). Va al final: un token inválido o un
    # dispositivo revocado siguen siendo un 401
    require_current_terms(request, user)

    return user


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UserResponseDTO | None:
    """
    El usuario de la sesión, o None si no hay sesión (release social 3, 28 oct 2026).

    Para lo que también ve un visitante: la clasificación por enlace. Sin token
    es un visitante; con un token caducado o inválido, el 401 de siempre, para
    que la app renueve la sesión en vez de enseñarle la vista de visitante.
    """
    if not read_access_token(request):
        return None
    return await get_current_user(request, credentials, uow)


def get_verify_email_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> VerifyEmailUseCase:
    """
    Proveedor del caso de uso VerifyEmailUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `VerifyEmailUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return VerifyEmailUseCase(uow)


def get_resend_verification_email_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
) -> ResendVerificationEmailUseCase:
    """
    Proveedor del caso de uso ResendVerificationEmailUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de emails de verificación.
    3. Crea una instancia de `ResendVerificationEmailUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ResendVerificationEmailUseCase(uow, email_service)


def get_request_password_reset_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
):
    """
    Proveedor del caso de uso RequestPasswordResetUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de emails de reseteo.
    3. Crea una instancia de `RequestPasswordResetUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RequestPasswordResetUseCase(uow, email_service)


def get_reset_password_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IEmailService = Depends(get_email_service),
):
    """
    Proveedor del caso de uso ResetPasswordUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Depende de `get_email_service` para envío de email de confirmación.
    3. Crea una instancia de `ResetPasswordUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ResetPasswordUseCase(uow, email_service)


def get_validate_reset_token_use_case(uow: UserUnitOfWorkInterface = Depends(get_uow)):
    """
    Proveedor del caso de uso ValidateResetTokenUseCase.

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ValidateResetTokenUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ValidateResetTokenUseCase(uow)


# ============================================================================
# COMPETITION MODULE - Dependency Injection
# ============================================================================


# Enrollment Use Cases


def get_competition_uow(
    session: AsyncSession = Depends(get_db_session),
) -> CompetitionUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo Competition.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyCompetitionUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `CompetitionUnitOfWorkInterface`.

    La UoW de Competition coordina 3 repositorios:
    - competitions: Repositorio de competiciones
    - enrollments: Repositorio de inscripciones
    - countries: Repositorio de países (shared domain)
    """
    return SQLAlchemyCompetitionUnitOfWork(session)


def get_golf_course_uow(
    session: AsyncSession = Depends(get_db_session),
) -> GolfCourseUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo Golf Course.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyGolfCourseUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `GolfCourseUnitOfWorkInterface`.

    La UoW de Golf Course coordina 2 repositorios:
    - golf_courses: Repositorio de campos de golf
    - countries: Repositorio de países (shared domain)
    """
    return SQLAlchemyGolfCourseUnitOfWork(session)


def get_social_uow(
    session: AsyncSession = Depends(get_db_session),
) -> SocialUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo Social.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemySocialUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `SocialUnitOfWorkInterface`.
    """
    return SQLAlchemySocialUnitOfWork(session)


def get_amigos(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
) -> AmigosInterface:
    """Los amigos de quien mira, del módulo social (release social 2)."""
    return AmigosAdapter(social_uow)


def get_eventos_de_amigos(
    social_uow: SocialUnitOfWorkInterface = Depends(get_social_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> EventosDeAmigosInterface:
    """La llave de una privada: amigos con evento en la Actividad de quien mira (27 oct)."""
    return EventosDeAmigosAdapter(social_uow, user_uow)


def get_social_email_service() -> ISocialEmailService:
    """Proveedor del servicio de email para el modulo Social (amistades)."""
    return EmailService()


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


def get_quick_match_uow(
    session: AsyncSession = Depends(get_db_session),
) -> QuickMatchUnitOfWorkInterface:
    """
    Proveedor de la Unit of Work para el módulo QuickMatch.

    Esta función:
    1. Depende de `get_db_session` para obtener una sesión de BD.
    2. Crea una instancia de `SQLAlchemyQuickMatchUnitOfWork` con esa sesión.
    3. Devuelve la instancia, cumpliendo con la interfaz `QuickMatchUnitOfWorkInterface`.
    """
    return SQLAlchemyQuickMatchUnitOfWork(session)


# ======================================================================================
# ADMIN PANEL USE CASE PROVIDERS
# ======================================================================================


def get_admin_list_users_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> AdminListUsersUseCase:
    """Proveedor del caso de uso AdminListUsersUseCase."""
    return AdminListUsersUseCase(uow)


def get_admin_update_user_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> AdminUpdateUserUseCase:
    """Proveedor del caso de uso AdminUpdateUserUseCase."""
    return AdminUpdateUserUseCase(uow)


def get_admin_set_user_active_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> AdminSetUserActiveUseCase:
    """Proveedor del caso de uso AdminSetUserActiveUseCase."""
    return AdminSetUserActiveUseCase(uow)


def get_admin_delete_user_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> AdminDeleteUserUseCase:
    """Proveedor del caso de uso AdminDeleteUserUseCase."""
    return AdminDeleteUserUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)


def get_get_admin_stats_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetAdminStatsUseCase:
    """Proveedor del caso de uso GetAdminStatsUseCase."""
    return GetAdminStatsUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)


def get_get_player_stats_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetPlayerStatsUseCase:
    """Proveedor del caso de uso GetPlayerStatsUseCase."""
    return GetPlayerStatsUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)


def get_get_recent_matches_use_case(
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    quick_match_uow: QuickMatchUnitOfWorkInterface = Depends(get_quick_match_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetRecentMatchesUseCase:
    """Proveedor del caso de uso GetRecentMatchesUseCase."""
    return GetRecentMatchesUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)


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


async def get_activity_db_session(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Una sesion propia para publicar en Actividad, aparte de la de la peticion.

    Todas las unidades de trabajo de una peticion comparten sesion. Actividad
    publica despues de que la accion se haya guardado, y si fallara en esa
    misma sesion su `rollback` caducaria todo lo que la accion tiene cargado:
    al montar la respuesta, la sesion asincrona intentaria recargarlo y la
    peticion acabaria en 500 con la accion hecha. Con su propia sesion —del
    mismo motor, otra conexion— un fallo de Actividad no toca nada de la
    accion. Se crea con el motor de la sesion de la peticion para usar la
    misma base de datos que ella (tambien en los tests).
    """
    async with AsyncSession(bind=session.bind, expire_on_commit=False) as propia:
        yield propia


@dataclass(frozen=True)
class ActivityUnitsOfWork:
    """Las unidades de trabajo con las que publica Actividad, sobre su propia sesion."""

    user: UserUnitOfWorkInterface
    competition: CompetitionUnitOfWorkInterface
    quick_match: QuickMatchUnitOfWorkInterface
    golf_course: GolfCourseUnitOfWorkInterface
    social: SocialUnitOfWorkInterface

    @property
    def differentials(self) -> PlayerDifferentialsInterface:
        return StatsPlayerDifferentialsAdapter(
            GetPlayerStatsUseCase(self.user, self.competition, self.quick_match, self.golf_course)
        )

    @property
    def history(self) -> PlayerCourseHistoryInterface:
        return PlayerCourseHistoryAdapter(self.quick_match, self.competition, self.golf_course)


def get_activity_units_of_work(
    session: AsyncSession = Depends(get_activity_db_session),
) -> ActivityUnitsOfWork:
    """Proveedor de las unidades de trabajo de Actividad (su sesion, no la de la peticion)."""
    return ActivityUnitsOfWork(
        user=SQLAlchemyUnitOfWork(session),
        competition=SQLAlchemyCompetitionUnitOfWork(session),
        quick_match=SQLAlchemyQuickMatchUnitOfWork(session),
        golf_course=SQLAlchemyGolfCourseUnitOfWork(session),
        social=SQLAlchemySocialUnitOfWork(session),
    )


def get_publish_round_achievements_use_case(
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
) -> PublishRoundAchievementsUseCase:
    """Proveedor del caso de uso PublishRoundAchievementsUseCase."""
    return PublishRoundAchievementsUseCase(
        social_uow=uows.social,
        quick_match_uow=uows.quick_match,
        golf_course_uow=uows.golf_course,
        user_uow=uows.user,
        differentials=uows.differentials,
        history=uows.history,
    )


def get_publish_tournament_achievements_use_case(
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
) -> PublishTournamentAchievementsUseCase:
    """Proveedor del caso de uso PublishTournamentAchievementsUseCase."""
    return PublishTournamentAchievementsUseCase(
        social_uow=uows.social,
        competition_uow=uows.competition,
        golf_course_uow=uows.golf_course,
        user_uow=uows.user,
        differentials=uows.differentials,
        history=uows.history,
    )


def get_tournament_achievements_publisher(
    publish_use_case: PublishTournamentAchievementsUseCase = Depends(
        get_publish_tournament_achievements_use_case
    ),
) -> TournamentAchievementsPublisherInterface:
    """Proveedor del adaptador que conecta competition con el feed social."""
    return TournamentAchievementsPublisher(publish_use_case)


def get_publish_quick_match_result_use_case(
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
) -> PublishQuickMatchResultUseCase:
    """Proveedor del caso de uso PublishQuickMatchResultUseCase (BE-2)."""
    return PublishQuickMatchResultUseCase(
        uows.social, uows.quick_match, uows.golf_course, uows.user
    )


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


def get_publish_competition_notices_use_case(
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
) -> PublishCompetitionNoticesUseCase:
    """Proveedor del caso de uso PublishCompetitionNoticesUseCase (BE-2)."""
    return PublishCompetitionNoticesUseCase(uows.social, uows.user)


def get_competition_activity_publisher(
    notices: PublishCompetitionNoticesUseCase = Depends(get_publish_competition_notices_use_case),
    uows: ActivityUnitsOfWork = Depends(get_activity_units_of_work),
    achievements: PublishTournamentAchievementsUseCase = Depends(
        get_publish_tournament_achievements_use_case
    ),
    round_achievements: PublishRoundAchievementsUseCase = Depends(
        get_publish_round_achievements_use_case
    ),
) -> CompetitionActivityPublisherInterface:
    """
    Proveedor del adaptador que lleva a Actividad lo de `competition` (BE-2).

    Con la general oficial a mano: la clasificacion final de cada uno sale de
    ella, no de otra cuenta; la de una Ryder, de su leaderboard oficial (I).
    Todo sobre la sesion propia de Actividad.
    """
    return CompetitionActivityPublisher(
        notices,
        ClasificacionGeneralUseCase(uow=uows.competition, user_repository=uows.user.users),
        uows.competition,
        ryder_scoreboard=GetLeaderboardUseCase(uows.competition, uows.user.users, ScoringService()),
        achievements=achievements,
        round_achievements=round_achievements,
    )


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


def get_scoring_service() -> ScoringService:
    """Proveedor del servicio de dominio ScoringService (match play + lo de la Ryder)."""
    return ScoringService()


def get_match_play_scoring() -> MatchPlayScoring:
    """Proveedor de las reglas del match play, sin lo de la Ryder (RyderCupAM#165)."""
    return MatchPlayScoring()


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


def get_location_builder(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> LocationBuilder:
    """
    Proveedor del domain service LocationBuilder.

    Reutiliza el mismo `uow` (y por tanto el mismo `uow.countries`) que reciben
    los use cases que lo consumen, ya que FastAPI cachea `Depends(get_competition_uow)`
    dentro de una misma request.
    """
    return LocationBuilder(uow.countries)


def get_create_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    location_builder: LocationBuilder = Depends(get_location_builder),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> CreateCompetitionUseCase:
    """
    Proveedor del caso de uso CreateCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Depende de `get_location_builder` para el domain service de ubicación.
    3. Crea una instancia de `CreateCompetitionUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return CreateCompetitionUseCase(uow, location_builder, user_uow.users)


def get_list_competitions_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListCompetitionsUseCase:
    """
    Proveedor del caso de uso ListCompetitionsUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ListCompetitionsUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    # La zona del campo hace falta para abrir las programadas a las que ya les
    # toca: verlas en un listado tambien las abre (BE #331). Sin esto el caso de
    # uso funciona igual pero no abre nada, y una competicion seguiria
    # anunciando «abre el martes» el miercoles
    return ListCompetitionsUseCase(
        uow,
        zona_del_campo=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
    )


def get_update_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    location_builder: LocationBuilder = Depends(get_location_builder),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> UpdateCompetitionUseCase:
    """
    Proveedor del caso de uso UpdateCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Depende de `get_location_builder` para el domain service de ubicación.
    3. Crea una instancia de `UpdateCompetitionUseCase` con esas dependencias.
    4. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return UpdateCompetitionUseCase(
        uow, location_builder, golf_course_uow.golf_courses, actividad=actividad
    )


def get_get_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetCompetitionUseCase:
    """
    Proveedor del caso de uso GetCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `GetCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    # La zona del campo hace falta para abrir las inscripciones a su hora (BE #319):
    # «las nueve» son las nueve de donde se juega
    return GetCompetitionUseCase(
        uow,
        zona_del_campo=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
    )


def get_competition_summary_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> GetCompetitionSummaryUseCase:
    """El resumen público de una competición (release social 3, L5)."""
    return GetCompetitionSummaryUseCase(uow)


def get_delete_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DeleteCompetitionUseCase:
    """
    Proveedor del caso de uso DeleteCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `DeleteCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return DeleteCompetitionUseCase(uow, actividad=actividad)


def get_activate_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ActivateCompetitionUseCase:
    """
    Proveedor del caso de uso ActivateCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ActivateCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ActivateCompetitionUseCase(uow)


_lanzador: LanzadorEnSegundoPlano | None = None


def get_lanzador_de_actualizaciones() -> LanzadorDeActualizaciones | None:
    """
    El lanzador de actualizaciones de hándicaps, uno para todo el proceso (#251).

    Solo con `HANDICAP_REFRESH_ENABLED` encendido y fuera de los tests: si no,
    al cerrar no se pregunta a la RFEG.
    """
    global _lanzador  # noqa: PLW0603 - uno por proceso, con sus tareas en marcha
    if not refresco_activado(os.environ):
        return None
    if _lanzador is None:
        _lanzador = LanzadorEnSegundoPlano(
            async_session_maker, RFEGHandicapService(timeout=10), EmailService()
        )
    return _lanzador


def get_coger_plaza_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CogerPlazaUseCase:
    """Coger plaza en una franja de stroke play (#251); quien deja una pierde su aviso de salida."""
    return CogerPlazaUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        actividad=actividad,
    )


def get_soltar_plaza_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SoltarPlazaUseCase:
    """Soltar la plaza en una franja de stroke play (#251); a quien la lista se la da, su aviso."""
    return SoltarPlazaUseCase(uow, actividad=actividad)


def get_reloj_del_servidor() -> Callable[[], datetime]:
    """
    El reloj del servidor para la anotación de las partidas (#251, PR 5).

    Decide si la anotación ya abrió; nunca una hora que mande el cliente. Es
    una dependencia para que los tests de la API puedan ponerlo en el día del
    torneo.
    """
    return lambda: datetime.now(UTC)


def get_anotar_hoyo_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> AnotarHoyoDePartidaUseCase:
    """Anotar un hoyo en una partida (#251): la zona del campo da la hora de apertura."""
    return AnotarHoyoDePartidaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
        actividad=actividad,
    )


def get_entregar_tarjeta_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> EntregarTarjetaDePartidaUseCase:
    """Entregar la tarjeta de una partida (#251)."""
    return EntregarTarjetaDePartidaUseCase(uow=uow)


def get_retirarse_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> RetirarseDePartidaUseCase:
    """Retirarse de una partida (#251)."""
    return RetirarseDePartidaUseCase(uow=uow)


def get_corregir_hoyo_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CorregirHoyoDePartidaUseCase:
    """El organizador corrige un hoyo de una partida (#251)."""
    return CorregirHoyoDePartidaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
        actividad=actividad,
    )


def get_reabrir_tarjeta_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> ReabrirTarjetaUseCase:
    """El organizador reabre una tarjeta (#251)."""
    return ReabrirTarjetaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_marcar_no_presentado_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> MarcarNoPresentadoUseCase:
    """El organizador marca a alguien como no presentado (#251); avisa a quien se recoloca (G3)."""
    return MarcarNoPresentadoUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
        actividad=actividad,
    )


def get_retirar_jugador_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> RetirarJugadorUseCase:
    """El organizador retira a quien ya jugó (#550)."""
    return RetirarJugadorUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_borrar_hoyo_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> BorrarHoyoDePartidaUseCase:
    """El organizador borra lo anotado en un hoyo (13 oct 2026)."""
    return BorrarHoyoDePartidaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_validar_lo_anotado_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> ValidarLoAnotadoUseCase:
    """El organizador valida lo anotado de quien juega sin marcador (QA del 11 oct 2026)."""
    return ValidarLoAnotadoUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_cerrar_franja_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> CerrarFranjaUseCase:
    """El organizador cierra las partidas de una franja (#251)."""
    return CerrarFranjaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        reloj=reloj,
    )


def get_clasificacion_de_la_franja_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> ClasificacionDeLaFranjaUseCase:
    """La clasificación de una franja (#251)."""
    return ClasificacionDeLaFranjaUseCase(uow=uow, user_repository=user_uow.users, eventos=eventos)


def get_clasificacion_general_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> ClasificacionGeneralUseCase:
    """La clasificación general de un stroke play (#251)."""
    return ClasificacionGeneralUseCase(uow=uow, user_repository=user_uow.users, eventos=eventos)


def get_clasificacion_scratch_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> ClasificacionScratchUseCase:
    """La clasificación scratch de un stroke play (#251)."""
    return ClasificacionScratchUseCase(uow=uow, user_repository=user_uow.users, eventos=eventos)


def get_ver_anotacion_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> VerAnotacionDePartidaUseCase:
    """La partida para anotar y las tarjetas de los suyos (#251), con la llave (27 oct)."""
    return VerAnotacionDePartidaUseCase(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        golf_courses=gc_uow.golf_courses,
        eventos=eventos,
    )


def get_jugadores_de_la_partida(
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> JugadoresDeLaPartida:
    """La foto de los jugadores de una partida (#251): campo y usuarios, misma sesión."""
    return JugadoresDeLaPartida(gc_uow.golf_courses, user_uow.users, PlayingHandicapCalculator())


def get_generar_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    jugadores: JugadoresDeLaPartida = Depends(get_jugadores_de_la_partida),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> GenerarPartidasUseCase:
    """Generar las partidas de una franja (#251): el campo da barras y zona horaria."""
    return GenerarPartidasUseCase(
        uow=uow,
        jugadores=jugadores,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


def get_mover_jugador_de_partida_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    jugadores: JugadoresDeLaPartida = Depends(get_jugadores_de_la_partida),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> MoverJugadorUseCase:
    """Mover a un jugador de partida (#251): quien no tenía, saca su foto con el campo."""
    return MoverJugadorUseCase(
        uow=uow,
        jugadores=jugadores,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


T = TypeVar("T")


def _de_las_partidas(
    caso_de_uso: Callable[..., T],
    uow: CompetitionUnitOfWorkInterface,
    gc_uow: GolfCourseUnitOfWorkInterface,
    user_uow: UserUnitOfWorkInterface,
    **extra: Any,
) -> T:
    """Los que solo necesitan la zona del campo y los nombres (#251); `extra`, lo de cada uno."""
    return caso_de_uso(
        uow=uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        user_repository=user_uow.users,
        reloj=lambda: datetime.now(UTC),
        **extra,
    )


def get_reordenar_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ReordenarPartidasUseCase:
    """Reordenar las partidas de una franja (#251): avisa a quien cambia de hora (G3)."""
    return _de_las_partidas(ReordenarPartidasUseCase, uow, gc_uow, user_uow, actividad=actividad)


def get_cambiar_marcadores_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> CambiarMarcadoresUseCase:
    """Cambiar los marcadores de una partida (#251)."""
    return _de_las_partidas(CambiarMarcadoresUseCase, uow, gc_uow, user_uow)


def get_borrar_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> BorrarPartidasUseCase:
    """Borrar las partidas de una franja (#251)."""
    return _de_las_partidas(BorrarPartidasUseCase, uow, gc_uow, user_uow, actividad=actividad)


def get_ver_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    amigos: AmigosInterface = Depends(get_amigos),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> VerPartidasUseCase:
    """Ver las partidas de una franja (#251), con los sin partida que deja ver la regla."""
    return _de_las_partidas(
        VerPartidasUseCase, uow, gc_uow, user_uow, amigos=amigos, eventos=eventos
    )


def get_mis_partidas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> MisPartidasUseCase:
    """Mis partidas en una competición (#251), con el nombre de su campo (BE #532)."""
    return MisPartidasUseCase(
        uow=uow, user_repository=user_uow.users, golf_courses=gc_uow.golf_courses
    )


def get_esperar_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> EsperarUseCase:
    """Apuntarse a la lista de espera de una franja (#251)."""
    return EsperarUseCase(uow)


def get_dejar_de_esperar_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DejarDeEsperarUseCase:
    """Salir de la lista de espera de una franja (#251); sin nada más, sale de la competición."""
    return DejarDeEsperarUseCase(uow, actividad=actividad)


def get_mis_plazas_asignadas_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> MisPlazasAsignadasUseCase:
    """Las plazas que asignó la lista de espera, para «Requiere tu atención» (#251)."""
    return MisPlazasAsignadasUseCase(uow)


def get_entendido_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> EntendidoUseCase:
    """«Entendido»: ya ha visto la plaza que le asignó la lista (#251)."""
    return EntendidoUseCase(uow)


def get_close_enrollments_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CloseEnrollmentsUseCase:
    """
    Proveedor del caso de uso CloseEnrollmentsUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CloseEnrollmentsUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    # Los usuarios, para el hándicap de cada inscrito en un stroke play; y el
    # refresco con la RFEG en segundo plano, solo en producción (#251)
    return CloseEnrollmentsUseCase(uow, user_uow.users, lanzador, actividad=actividad)


def get_actualizar_handicaps_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
) -> ActualizarHandicapsUseCase:
    """El botón «Actualizar hándicaps» del organizador (#251): la zona da la hora de salida."""
    return ActualizarHandicapsUseCase(
        uow,
        CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        lanzador,
        reloj=lambda: datetime.now(UTC),
    )


def get_programar_actualizacion_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
) -> ProgramarActualizacionUseCase:
    """Programar la actualización de hándicaps (#251): la ventana se mira en esa hora."""
    return ProgramarActualizacionUseCase(
        uow,
        CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        refresco_activo=lanzador is not None,
    )


def get_anular_programacion_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> AnularProgramacionUseCase:
    """Anular la actualización de hándicaps programada (#251)."""
    return AnularProgramacionUseCase(uow)


def get_ventana_de_actualizacion_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
) -> VentanaDeActualizacionUseCase:
    """Si el organizador puede actualizar ahora los hándicaps, para la ficha (#251)."""
    return VentanaDeActualizacionUseCase(
        uow,
        CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        refresco_activo=lanzador is not None,
    )


def get_handicap_update_status_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> GetHandicapUpdateStatusUseCase:
    """La última actualización de hándicaps, para la ficha del organizador (#251)."""
    return GetHandicapUpdateStatusUseCase(uow, user_uow.users)


def get_name_captains_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    lanzador: LanzadorDeActualizaciones | None = Depends(get_lanzador_de_actualizaciones),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> NameCaptainsUseCase:
    """Proveedor del caso de uso NameCaptainsUseCase (BE #320), con el refresco (#251)."""
    return NameCaptainsUseCase(uow, lanzador, actividad=actividad)


def get_name_vice_captain_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> NameViceCaptainUseCase:
    """Proveedor del caso de uso NameViceCaptainUseCase (BE #320)."""
    return NameViceCaptainUseCase(uow)


def get_fill_captain_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> FillCaptainUseCase:
    """Proveedor del caso de uso FillCaptainUseCase (BE #320)."""
    return FillCaptainUseCase(uow)


def get_start_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> StartCompetitionUseCase:
    """
    Proveedor del caso de uso StartCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `StartCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    # Los usuarios, para nombrar a quien no tenga franja en un stroke play (#251)
    return StartCompetitionUseCase(uow, user_uow.users, actividad=actividad)


def get_complete_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    achievements: TournamentAchievementsPublisherInterface = Depends(
        get_tournament_achievements_publisher
    ),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CompleteCompetitionUseCase:
    """
    Proveedor del caso de uso CompleteCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CompleteCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.

    Cerrar el torneo es lo que dispara el feed de logros (BE #175), de ahí el
    publicador.
    """
    return CompleteCompetitionUseCase(uow, achievements, actividad=actividad)


def get_cancel_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CancelCompetitionUseCase:
    """
    Proveedor del caso de uso CancelCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `CancelCompetitionUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return CancelCompetitionUseCase(uow, actividad=actividad)


def get_revert_competition_status_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> RevertCompetitionStatusUseCase:
    """
    Proveedor del caso de uso RevertCompetitionStatusUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `RevertCompetitionStatusUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RevertCompetitionStatusUseCase(uow)


def get_revert_competition_to_in_progress_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RevertCompetitionToInProgressUseCase:
    """
    Proveedor del caso de uso RevertCompetitionToInProgressUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `RevertCompetitionToInProgressUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return RevertCompetitionToInProgressUseCase(uow, actividad=actividad)


def get_reopen_enrollments_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ReopenEnrollmentsUseCase:
    """
    Proveedor del caso de uso ReopenEnrollmentsUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ReopenEnrollmentsUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint de la API.
    """
    return ReopenEnrollmentsUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


def get_add_golf_course_to_competition_use_case(
    competition_uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    golf_course_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> AddGolfCourseToCompetitionUseCase:
    """
    Proveedor del caso de uso AddGolfCourseToCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` y `get_golf_course_uow`.
    2. Crea una instancia de `AddGolfCourseToCompetitionUseCase` con ambas dependencias.
    3. El golf_course_repository se obtiene desde golf_course_uow.golf_courses.
    """
    return AddGolfCourseToCompetitionUseCase(
        uow=competition_uow,
        golf_course_repository=golf_course_uow.golf_courses,
    )


def get_remove_golf_course_from_competition_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> RemoveGolfCourseFromCompetitionUseCase:
    """
    Proveedor del caso de uso RemoveGolfCourseFromCompetitionUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `RemoveGolfCourseFromCompetitionUseCase` con esa dependencia.
    """
    return RemoveGolfCourseFromCompetitionUseCase(uow)


def get_reorder_golf_courses_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ReorderGolfCoursesUseCase:
    """
    Proveedor del caso de uso ReorderGolfCoursesUseCase.

    Esta función:
    1. Depende de `get_competition_uow` para obtener una Unit of Work.
    2. Crea una instancia de `ReorderGolfCoursesUseCase` con esa dependencia.
    """
    return ReorderGolfCoursesUseCase(uow)


# ======================================================================================
# ENROLLMENT USE CASE PROVIDERS
# ======================================================================================


def get_request_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RequestEnrollmentUseCase:
    """Apuntarse a una pública (28 oct 2026): abre la programada si toca y avisa."""
    return RequestEnrollmentUseCase(
        uow,
        user_uow.users,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        actividad=actividad,
    )


def get_direct_enroll_player_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DirectEnrollPlayerUseCase:
    """Proveedor del caso de uso DirectEnrollPlayerUseCase."""
    return DirectEnrollPlayerUseCase(uow, user_uow.users, actividad=actividad)


def get_handle_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> HandleEnrollmentUseCase:
    """Proveedor del caso de uso HandleEnrollmentUseCase."""
    return HandleEnrollmentUseCase(uow, user_uow.users, actividad=actividad)


def get_cancel_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> CancelEnrollmentUseCase:
    """Proveedor del caso de uso CancelEnrollmentUseCase."""
    return CancelEnrollmentUseCase(uow)


def get_withdraw_enrollment_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> WithdrawEnrollmentUseCase:
    """Proveedor del caso de uso WithdrawEnrollmentUseCase."""
    return WithdrawEnrollmentUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


def get_remove_enrolled_player_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RemoveEnrolledPlayerUseCase:
    """Proveedor del caso de uso RemoveEnrolledPlayerUseCase (release social 2)."""
    return RemoveEnrolledPlayerUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=lambda: datetime.now(UTC),
        actividad=actividad,
    )


def get_update_stroke_play_settings_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> UpdateStrokePlaySettingsUseCase:
    """Proveedor del caso de uso UpdateStrokePlaySettingsUseCase (#251)."""
    return UpdateStrokePlaySettingsUseCase(uow)


def get_set_custom_handicap_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> SetCustomHandicapUseCase:
    """Proveedor del caso de uso SetCustomHandicapUseCase."""
    return SetCustomHandicapUseCase(uow)


def get_set_name_preference_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> SetNamePreferenceUseCase:
    """Proveedor del caso de uso SetNamePreferenceUseCase."""
    return SetNamePreferenceUseCase(uow)


def get_remove_custom_handicap_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RemoveCustomHandicapUseCase:
    """Proveedor del caso de uso RemoveCustomHandicapUseCase."""
    # Los usuarios: en un stroke play nadie se queda sin hándicap (#251)
    return RemoveCustomHandicapUseCase(uow, user_uow.users)


def get_list_enrollments_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    amigos: AmigosInterface = Depends(get_amigos),
) -> ListEnrollmentsUseCase:
    """Proveedor del caso de uso ListEnrollmentsUseCase (con quién ve a quién)."""
    return ListEnrollmentsUseCase(uow, amigos)


# ======================================================================================
# ROUND, MATCH & TEAM ASSIGNMENT USE CASE PROVIDERS (Sprint 2 - Block 7)
# ======================================================================================


def get_create_round_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
) -> CreateRoundUseCase:
    """Proveedor del caso de uso CreateRoundUseCase: con la zona, para no crear una franja pasada."""
    return CreateRoundUseCase(
        uow,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
    )


def get_update_round_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    jugadores: JugadoresDeLaPartida = Depends(get_jugadores_de_la_partida),
    reloj: Callable[[], datetime] = Depends(get_reloj_del_servidor),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> UpdateRoundUseCase:
    """Proveedor del caso de uso UpdateRoundUseCase: con el campo, rehace las partidas (#251)."""
    return UpdateRoundUseCase(
        uow,
        jugadores=jugadores,
        zonas=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        reloj=reloj,
        actividad=actividad,
    )


def get_delete_round_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DeleteRoundUseCase:
    """Proveedor del caso de uso DeleteRoundUseCase (olvida en Actividad lo de la ronda)."""
    return DeleteRoundUseCase(uow, actividad=actividad)


def get_get_schedule_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
    amigos: AmigosInterface = Depends(get_amigos),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> GetScheduleUseCase:
    """Proveedor del caso de uso GetScheduleUseCase (cross-module: Competition + GolfCourse).

    Lleva la mesa de sobres: mirar la agenda abre los que ya tocan, como mirar
    la página del sobre (BE #367).
    """
    return GetScheduleUseCase(
        uow,
        gc_uow.golf_courses,
        sobres=EnvelopeDesk(
            uow,
            user_uow.users,
            timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
            generador=_generador_al_abrir(uow, gc_uow, user_uow, scoring_service, actividad),
        ),
        amigos=amigos,
        eventos=eventos,
    )


def get_get_match_detail_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> GetMatchDetailUseCase:
    """Proveedor del caso de uso GetMatchDetailUseCase, con la llave (27 oct)."""
    return GetMatchDetailUseCase(uow, eventos=eventos)


def get_update_match_status_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> UpdateMatchStatusUseCase:
    """Proveedor del caso de uso UpdateMatchStatusUseCase."""
    return UpdateMatchStatusUseCase(uow, actividad=actividad)


def get_declare_walkover_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> DeclareWalkoverUseCase:
    """Proveedor del caso de uso DeclareWalkoverUseCase."""
    return DeclareWalkoverUseCase(uow, actividad=actividad)


def get_configure_schedule_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ConfigureScheduleUseCase:
    """Proveedor del caso de uso ConfigureScheduleUseCase (olvida en Actividad lo sustituido)."""
    return ConfigureScheduleUseCase(
        uow, schedule_format_service=ScheduleFormatService(), actividad=actividad
    )


def get_assign_teams_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> AssignTeamsUseCase:
    """Proveedor del caso de uso AssignTeamsUseCase (cross-module: Competition + User)."""
    return AssignTeamsUseCase(
        uow=uow,
        user_repository=user_uow.users,
        snake_draft_service=SnakeDraftService(),
    )


def get_undo_teams_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> UndoTeamsUseCase:
    """Proveedor del caso de uso UndoTeamsUseCase (30 oct 2026)."""
    return UndoTeamsUseCase(uow=uow)


def get_start_draft_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> StartDraftUseCase:
    """Proveedor del caso de uso StartDraftUseCase (FE #653)."""
    return StartDraftUseCase(uow=uow, user_repository=user_uow.users)


def get_draft_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> GetDraftUseCase:
    """Proveedor del caso de uso GetDraftUseCase (FE #653)."""
    return GetDraftUseCase(uow=uow, user_repository=user_uow.users)


def get_make_draft_pick_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> MakeDraftPickUseCase:
    """Proveedor del caso de uso MakeDraftPickUseCase (FE #653)."""
    return MakeDraftPickUseCase(uow=uow, user_repository=user_uow.users)


def _construir_generador(
    uow, gc_uow, user_uow, scoring_service, handicap_service=None, actividad=None
) -> GenerateMatchesUseCase:
    """El unico sitio que monta GenerateMatchesUseCase.

    Lo usan el boton de «Generar» y la apertura de los sobres (BE #361): con
    dos sitios, una dependencia nueva del constructor se olvidaria en uno y la
    generacion automatica saldria cableada distinta sin que nadie lo notara.
    """
    return GenerateMatchesUseCase(
        uow=uow,
        golf_course_repository=gc_uow.golf_courses,
        user_repository=user_uow.users,
        handicap_calculator=PlayingHandicapCalculator(),
        scoring_service=scoring_service,
        handicap_service=handicap_service,
        actividad=actividad,
    )


def _generador_al_abrir(
    uow, gc_uow, user_uow, scoring_service, actividad=None
) -> GenerateMatchesUseCase:
    """Lo que crea los partidos al abrirse los sobres (BE #361).

    Sobre la MISMA Unit of Work que el caso de uso de los sobres: abrirlos y
    crear los partidos van en una transaccion. Sin servicio de handicap: al
    abrir no se pregunta a la RFEG, que seria una llamada de red por jugador
    dentro de la lectura de la pantalla.
    """
    return _construir_generador(uow, gc_uow, user_uow, scoring_service, actividad=actividad)


def get_list_my_sessions_without_matches_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
) -> ListMySessionsWithoutMatchesUseCase:
    """Proveedor del caso de uso ListMySessionsWithoutMatchesUseCase (BE #361)."""
    return ListMySessionsWithoutMatchesUseCase(uow)


def get_submit_envelope_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SubmitEnvelopeUseCase:
    """Proveedor del caso de uso SubmitEnvelopeUseCase (FE #655).

    Lleva la zona del campo porque entregar mira el plazo: pasada la hora los
    sobres se abren y la entrega llega tarde.
    """
    return SubmitEnvelopeUseCase(
        uow,
        user_uow.users,
        timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        generador=_generador_al_abrir(uow, gc_uow, user_uow, scoring_service, actividad),
    )


def get_envelopes_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> GetEnvelopesUseCase:
    """Proveedor del caso de uso GetEnvelopesUseCase (FE #655).

    Lleva la zona del campo porque mirar los sobres es lo que los abre cuando
    llega su hora —6 horas antes de la sesion—, sin ningun proceso de fondo.
    """
    return GetEnvelopesUseCase(
        uow,
        user_uow.users,
        timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        generador=_generador_al_abrir(uow, gc_uow, user_uow, scoring_service, actividad),
    )


def get_reveal_envelopes_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RevealEnvelopesUseCase:
    """Proveedor del caso de uso RevealEnvelopesUseCase (FE #655).

    El repositorio de usuarios es para el handicap del sobre que haya que
    rellenar: el propio de la inscripcion si lo tiene, y si no el del jugador.

    La zona del campo es para saber si esta sesion llega a tener plazo: la que
    no lo tiene —campo sin zona— no se abre sola nunca, y ahi el organizador
    conserva la llave. Sin este cableado esa sesion se quedaria atascada.
    """
    return RevealEnvelopesUseCase(
        uow,
        user_uow.users,
        timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
        generador=_generador_al_abrir(uow, gc_uow, user_uow, scoring_service, actividad),
    )


def get_list_my_pending_envelopes_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListMyPendingEnvelopesUseCase:
    """Proveedor del caso de uso ListMyPendingEnvelopesUseCase (FE #655).

    La hora la pone el SERVIDOR: con la del movil, un telefono atrasado
    resucitaria avisos de sesiones ya jugadas. Y la zona del campo es lo que
    convierte la franja en una hora, que es contra lo que se mide el plazo.
    """
    return ListMyPendingEnvelopesUseCase(
        uow,
        timezone_service=CompetitionTimezoneFromCourse(gc_uow.golf_courses, uow.competitions),
    )


def get_reset_envelopes_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ResetEnvelopesUseCase:
    """Proveedor del caso de uso ResetEnvelopesUseCase (FE #655).

    Sin zona horaria: rehacer los sobres no mira ningun reloj, solo que no se
    haya jugado nada de esa sesion.
    """
    return ResetEnvelopesUseCase(uow, user_uow.users, actividad=actividad)


def get_generate_matches_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    handicap_service: HandicapService = Depends(get_handicap_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> GenerateMatchesUseCase:
    """Proveedor del caso de uso GenerateMatchesUseCase (cross-module: Competition + GolfCourse + User)."""
    return _construir_generador(uow, gc_uow, user_uow, scoring_service, handicap_service, actividad)


def get_reassign_match_players_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ReassignMatchPlayersUseCase:
    """Proveedor del caso de uso ReassignMatchPlayersUseCase (cross-module: Competition + GolfCourse + User)."""
    return ReassignMatchPlayersUseCase(
        uow=uow,
        golf_course_repository=gc_uow.golf_courses,
        user_repository=user_uow.users,
        handicap_calculator=PlayingHandicapCalculator(),
        scoring_service=scoring_service,
        actividad=actividad,
    )


# ======================================================================================
# INVITATION USE CASE PROVIDERS (Sprint 3 - Block 2)
# ======================================================================================


def get_invitation_email_service() -> IInvitationEmailService:
    """Proveedor del servicio de email para invitaciones."""
    return EmailService()


def get_send_invitation_by_user_id_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IInvitationEmailService = Depends(get_invitation_email_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SendInvitationByUserIdUseCase:
    """Proveedor del caso de uso SendInvitationByUserIdUseCase."""
    return SendInvitationByUserIdUseCase(uow, user_uow, email_service, actividad=actividad)


def get_send_invitation_by_email_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    email_service: IInvitationEmailService = Depends(get_invitation_email_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SendInvitationByEmailUseCase:
    """Proveedor del caso de uso SendInvitationByEmailUseCase."""
    return SendInvitationByEmailUseCase(uow, user_uow, email_service, actividad=actividad)


def get_list_my_invitations_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListMyInvitationsUseCase:
    """Proveedor del caso de uso ListMyInvitationsUseCase."""
    return ListMyInvitationsUseCase(uow, user_uow)


def get_respond_to_invitation_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> RespondToInvitationUseCase:
    """Proveedor del caso de uso RespondToInvitationUseCase."""
    return RespondToInvitationUseCase(uow, user_uow, actividad=actividad)


def get_cancel_invitation_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> CancelInvitationUseCase:
    """Proveedor del caso de uso CancelInvitationUseCase (BE #359)."""
    return CancelInvitationUseCase(uow, actividad=actividad)


def get_list_competition_invitations_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ListCompetitionInvitationsUseCase:
    """Proveedor del caso de uso ListCompetitionInvitationsUseCase."""
    return ListCompetitionInvitationsUseCase(uow, user_uow, actividad=actividad)


# ======================================================================================
# SCORING USE CASE PROVIDERS (Sprint 4 - Live Scoring)
# ======================================================================================


def get_get_scoring_view_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> GetScoringViewUseCase:
    """Proveedor del caso de uso GetScoringViewUseCase (cross-module: Competition + GolfCourse + User)."""
    return GetScoringViewUseCase(
        uow, user_uow.users, scoring_service, gc_uow.golf_courses, eventos=eventos
    )


def get_submit_hole_score_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SubmitHoleScoreUseCase:
    """Proveedor del caso de uso SubmitHoleScoreUseCase (cross-module: Competition + GolfCourse + User)."""
    return SubmitHoleScoreUseCase(
        uow, user_uow.users, scoring_service, gc_uow.golf_courses, actividad=actividad
    )


def get_submit_scorecard_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    gc_uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> SubmitScorecardUseCase:
    """Proveedor del caso de uso SubmitScorecardUseCase (el campo, para el par de la raya)."""
    return SubmitScorecardUseCase(
        uow, scoring_service, actividad=actividad, golf_course_repo=gc_uow.golf_courses
    )


def get_get_leaderboard_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    user_uow: UserUnitOfWorkInterface = Depends(get_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    eventos: EventosDeAmigosInterface = Depends(get_eventos_de_amigos),
) -> GetLeaderboardUseCase:
    """Proveedor del caso de uso GetLeaderboardUseCase, con la llave (27 oct)."""
    return GetLeaderboardUseCase(uow, user_uow.users, scoring_service, eventos=eventos)


def get_concede_match_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
    actividad: CompetitionActivityPublisherInterface = Depends(get_competition_activity_publisher),
) -> ConcedeMatchUseCase:
    """Proveedor del caso de uso ConcedeMatchUseCase."""
    return ConcedeMatchUseCase(uow, scoring_service, actividad=actividad)


def get_withdraw_match_player_use_case(
    uow: CompetitionUnitOfWorkInterface = Depends(get_competition_uow),
    scoring_service: ScoringService = Depends(get_scoring_service),
) -> WithdrawMatchPlayerUseCase:
    """Proveedor de WithdrawMatchPlayerUseCase (fourball con un jugador retirado)."""
    return WithdrawMatchPlayerUseCase(uow, scoring_service)


# ============================================================================
# Account Lockout Use Cases (v1.13.0)
# ============================================================================


def get_unlock_account_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UnlockAccountUseCase:
    """Proveedor del caso de uso UnlockAccountUseCase (v1.13.0 - Account Lockout)."""
    return UnlockAccountUseCase(uow)


# ============================================================================
# SUPPORT MODULE - Dependency Injection
# ============================================================================


def get_github_issue_service():
    """Proveedor del servicio de GitHub Issues."""
    return GitHubIssueService()


def get_submit_contact_use_case(
    github_issue_service=Depends(get_github_issue_service),
):
    """Proveedor del caso de uso SubmitContactUseCase."""
    return SubmitContactUseCase(github_issue_service)


# ============================================================================
# GOLF COURSE MODULE - Dependency Injection
# ============================================================================


def get_request_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RequestGolfCourseUseCase:
    """Proveedor del caso de uso RequestGolfCourseUseCase."""
    return RequestGolfCourseUseCase(uow, TzfpyTimezoneResolver())


def get_get_golf_course_by_id_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetGolfCourseByIdUseCase:
    """Proveedor del caso de uso GetGolfCourseByIdUseCase."""
    return GetGolfCourseByIdUseCase(uow)


def get_list_approved_golf_courses_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListApprovedGolfCoursesUseCase:
    """Proveedor del caso de uso ListApprovedGolfCoursesUseCase."""
    return ListApprovedGolfCoursesUseCase(uow)


def get_list_pending_golf_courses_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListPendingGolfCoursesUseCase:
    """Proveedor del caso de uso ListPendingGolfCoursesUseCase."""
    return ListPendingGolfCoursesUseCase(uow)


def get_approve_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ApproveGolfCourseUseCase:
    """Proveedor del caso de uso ApproveGolfCourseUseCase."""
    return ApproveGolfCourseUseCase(uow)


def get_reject_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RejectGolfCourseUseCase:
    """Proveedor del caso de uso RejectGolfCourseUseCase."""
    return RejectGolfCourseUseCase(uow)


def get_create_direct_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> CreateDirectGolfCourseUseCase:
    """Proveedor del caso de uso CreateDirectGolfCourseUseCase."""
    return CreateDirectGolfCourseUseCase(uow, TzfpyTimezoneResolver())


def get_update_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> UpdateGolfCourseUseCase:
    """Proveedor del caso de uso UpdateGolfCourseUseCase."""
    return UpdateGolfCourseUseCase(uow, TzfpyTimezoneResolver())


def get_approve_update_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ApproveUpdateGolfCourseUseCase:
    """Proveedor del caso de uso ApproveUpdateGolfCourseUseCase."""
    return ApproveUpdateGolfCourseUseCase(uow)


def get_reject_update_golf_course_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RejectUpdateGolfCourseUseCase:
    """Proveedor del caso de uso RejectUpdateGolfCourseUseCase."""
    return RejectUpdateGolfCourseUseCase(uow)


# Mapa de hoyos (BE #532)


def get_approved_hole_map_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetApprovedHoleMapUseCase:
    """Proveedor del caso de uso GetApprovedHoleMapUseCase."""
    return GetApprovedHoleMapUseCase(uow)


def get_list_pending_hole_maps_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListPendingHoleMapsUseCase:
    """Proveedor del caso de uso ListPendingHoleMapsUseCase."""
    return ListPendingHoleMapsUseCase(uow)


def get_hole_map_for_review_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetHoleMapForReviewUseCase:
    """Proveedor del caso de uso GetHoleMapForReviewUseCase."""
    return GetHoleMapForReviewUseCase(uow)


def get_approve_hole_map_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ApproveHoleMapUseCase:
    """Proveedor del caso de uso ApproveHoleMapUseCase."""
    return ApproveHoleMapUseCase(uow)


def get_reject_hole_map_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> RejectHoleMapUseCase:
    """Proveedor del caso de uso RejectHoleMapUseCase."""
    return RejectHoleMapUseCase(uow)


# Una sola para todo el proceso: la ventana de 10 minutos por jugador tiene que
# verse entre peticiones. Vive solo en memoria (BE #532, 16 oct 2026)
_recent_hole_sample_senders = InMemoryRecentHoleSampleSenders()


def get_recent_hole_sample_senders() -> IRecentHoleSampleSenders:
    """Proveedor de quién aportó hace poco una muestra de hoyo (singleton del proceso)."""
    return _recent_hole_sample_senders


def get_submit_hole_sample_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    recent_senders: IRecentHoleSampleSenders = Depends(get_recent_hole_sample_senders),
) -> SubmitHoleSampleUseCase:
    """Proveedor del caso de uso SubmitHoleSampleUseCase."""
    return SubmitHoleSampleUseCase(uow, recent_senders)


# Otra ventana, aparte de la de las muestras: reportar un hoyo no gasta el hueco
# de su muestra, ni al revés (entrega 7)
_recent_hole_report_senders = InMemoryRecentHoleSampleSenders()


def get_recent_hole_report_senders() -> IRecentHoleSampleSenders:
    """Proveedor de quién reportó hace poco un hoyo (singleton del proceso)."""
    return _recent_hole_report_senders


def get_submit_hole_report_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
    recent_senders: IRecentHoleSampleSenders = Depends(get_recent_hole_report_senders),
) -> SubmitHoleReportUseCase:
    """Proveedor del caso de uso SubmitHoleReportUseCase (entrega 7)."""
    return SubmitHoleReportUseCase(uow, recent_senders)


def get_discard_hole_report_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> DiscardHoleReportUseCase:
    """Proveedor del caso de uso DiscardHoleReportUseCase (entrega 7)."""
    return DiscardHoleReportUseCase(uow)


def get_list_hole_samples_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListHoleSamplesUseCase:
    """Proveedor del caso de uso ListHoleSamplesUseCase."""
    return ListHoleSamplesUseCase(uow)


def get_save_hole_line_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> SaveHoleLineUseCase:
    """Proveedor del caso de uso SaveHoleLineUseCase (BE #575)."""
    return SaveHoleLineUseCase(uow)


def get_reopen_hole_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ReopenHoleUseCase:
    """Proveedor del caso de uso ReopenHoleUseCase (BE #575)."""
    return ReopenHoleUseCase(uow)


def get_list_hole_reviews_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> ListHoleReviewsUseCase:
    """Proveedor del caso de uso ListHoleReviewsUseCase (BE #575)."""
    return ListHoleReviewsUseCase(uow)


def get_hole_review_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> GetHoleReviewUseCase:
    """Proveedor del caso de uso GetHoleReviewUseCase (BE #575)."""
    return GetHoleReviewUseCase(uow)


def get_delete_hole_sample_use_case(
    uow: GolfCourseUnitOfWorkInterface = Depends(get_golf_course_uow),
) -> DeleteHoleSampleUseCase:
    """Proveedor del caso de uso DeleteHoleSampleUseCase (BE #575)."""
    return DeleteHoleSampleUseCase(uow)


# ============================================================================
# Device Fingerprinting Use Cases (v1.13.0)
# ============================================================================


def get_list_user_devices_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> ListUserDevicesUseCase:
    """
    Proveedor del caso de uso ListUserDevicesUseCase (v1.13.0 - Device Fingerprinting).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (user_devices repository).
    2. Crea una instancia de `ListUserDevicesUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint GET /users/me/devices.
    """
    return ListUserDevicesUseCase(uow)


def get_revoke_device_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> RevokeDeviceUseCase:
    """
    Proveedor del caso de uso RevokeDeviceUseCase (v1.13.0 - Device Fingerprinting).

    Esta función:
    1. Depende de `get_uow` para obtener una Unit of Work (user_devices repository).
    2. Crea una instancia de `RevokeDeviceUseCase` con esa dependencia.
    3. Devuelve la instancia lista para ser usada por el endpoint DELETE /users/me/devices/{id}.
    """
    return RevokeDeviceUseCase(uow)


# ============================================================================
# Google OAuth Use Cases (Sprint 3)
# ============================================================================


def get_google_oauth_service() -> IGoogleOAuthService:
    """Proveedor del servicio de Google OAuth."""
    return GoogleOAuthService()


def get_google_login_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    token_service: ITokenService = Depends(get_token_service),
    google_oauth_service: IGoogleOAuthService = Depends(get_google_oauth_service),
    register_device_use_case: RegisterDeviceUseCase = Depends(get_register_device_use_case),
) -> GoogleLoginUseCase:
    """Proveedor del caso de uso GoogleLoginUseCase."""
    return GoogleLoginUseCase(uow, token_service, google_oauth_service, register_device_use_case)


def get_link_google_account_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
    google_oauth_service: IGoogleOAuthService = Depends(get_google_oauth_service),
) -> LinkGoogleAccountUseCase:
    """Proveedor del caso de uso LinkGoogleAccountUseCase."""
    return LinkGoogleAccountUseCase(uow, google_oauth_service)


def get_unlink_google_account_use_case(
    uow: UserUnitOfWorkInterface = Depends(get_uow),
) -> UnlinkGoogleAccountUseCase:
    """Proveedor del caso de uso UnlinkGoogleAccountUseCase."""
    return UnlinkGoogleAccountUseCase(uow)
