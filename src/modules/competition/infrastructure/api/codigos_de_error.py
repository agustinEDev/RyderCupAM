"""
Errores del módulo competition que la API traduce a su código HTTP en un solo sitio.

La respuesta es la que daba cada ruta con su `except X: raise HTTPException(código, str(e))`:
el código de aquí y {"detail": str(e)}. Lo registra la composition root
(`src/config/codigos_de_error.py`). Un error que en alguna ruta da otro código, o un texto
propio, se sigue traduciendo en esa ruta.
"""

from fastapi import status

from src.modules.competition.application.exceptions import (
    AgendaNotEditableError,
    CompetitionAlreadyExistsError,
    CompetitionFullError,
    CompetitionNotClosedError,
    CompetitionNotDraftError,
    CompetitionNotFoundError,
    DateOutOfRangeError,
    EnrollmentNotFoundError,
    FranjaInvalidaError,
    GolfCourseHasRoundsError,
    HandicapEditNotAllowedError,
    InvalidHoleNumberError,
    InvalidTeeColorError,
    InvitationNotFoundError,
    InviteeNotFoundError,
    MatchNotFoundError,
    MatchNotScoringError,
    NotCompetitionCreatorError,
    NotCompetitionParticipantError,
    NotCreatorError,
    NotInviteeError,
    NotMatchPlayerError,
    PartidaNotFoundError,
    PlazaEnFranjaError,
    RoundNotFoundError,
    RoundNotModifiableError,
    ScheduleAlreadyInPlayError,
    ScorecardAlreadySubmittedError,
    ScorecardNotReadyError,
)
from src.modules.competition.application.services.envelope_pairings import (
    EnvelopesDecideThePairingsError,
    EnvelopesNotRevealedError,
)
from src.modules.competition.application.services.genero_obligatorio import PerfilIncompletoError
from src.modules.competition.application.services.jugadores_del_partido import (
    PlayerNotEnrolledError,
)
from src.modules.competition.application.services.match_players_builder import TeeColorNotFoundError
from src.modules.competition.application.use_cases.add_golf_course_use_case import (
    GolfCourseNotFoundError,
)
from src.modules.competition.application.use_cases.cancel_enrollment_use_case import (
    NotOwnerError as CancelEnrollmentNotOwnerError,
)
from src.modules.competition.application.use_cases.configure_schedule_use_case import (
    NoGolfCoursesError,
)
from src.modules.competition.application.use_cases.create_round_use_case import (
    DuplicateSessionError as CreateRoundDuplicateSessionError,
    GolfCourseNotInCompetitionError as CreateRoundGolfCourseNotInCompetitionError,
)
from src.modules.competition.application.use_cases.declare_walkover_use_case import (
    CompetitionNotInProgressError as DeclareWalkoverCompetitionNotInProgressError,
    InvalidWalkoverError,
)
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    AlreadyEnrolledError as DirectEnrollPlayerAlreadyEnrolledError,
    CompetitionNotActiveError as DirectEnrollPlayerCompetitionNotActiveError,
)
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    RoundNotPendingMatchesError,
)
from src.modules.competition.application.use_cases.name_vice_captain_use_case import (
    NotCaptainOrCreatorError,
)
from src.modules.competition.application.use_cases.reassign_match_players_use_case import (
    MatchNotScheduledError,
    NoTeamAssignmentError,
    PlayerNotInTeamError,
    WrongNumberOfPlayersError,
)
from src.modules.competition.application.use_cases.remove_golf_course_use_case import (
    GolfCourseNotAssignedError,
)
from src.modules.competition.application.use_cases.reorder_golf_courses_use_case import (
    InvalidReorderError,
)
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    AlreadyEnrolledError as RequestEnrollmentAlreadyEnrolledError,
    CompetitionIsPrivateError,
    CompetitionNotActiveError as RequestEnrollmentCompetitionNotActiveError,
    EnrollmentClosedError,
    TooManyEnrollmentsError,
)
from src.modules.competition.application.use_cases.reset_envelopes_use_case import (
    NothingToResetError,
    SessionAlreadyPlayedError,
)
from src.modules.competition.application.use_cases.reveal_envelopes_use_case import (
    EarlyRevealNeedsBothCaptainsError,
)
from src.modules.competition.application.use_cases.set_name_preference_use_case import (
    NotOwnerError as SetNamePreferenceNotOwnerError,
)
from src.modules.competition.application.use_cases.submit_envelope_use_case import (
    NotATeamCaptainError,
)
from src.modules.competition.application.use_cases.update_match_status_use_case import (
    CompetitionNotInProgressError as UpdateMatchStatusCompetitionNotInProgressError,
    InvalidActionError,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    DuplicateSessionError as UpdateRoundDuplicateSessionError,
    GolfCourseNotInCompetitionError as UpdateRoundGolfCourseNotInCompetitionError,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    NotOwnerError as WithdrawEnrollmentNotOwnerError,
)
from src.modules.competition.domain.entities.competition import TournamentTypeError
from src.modules.competition.domain.entities.draft import NotYourTurnError
from src.modules.competition.domain.entities.enrollment import EnrollmentStateError
from src.modules.competition.domain.exceptions.competition_violations import (
    AlreadyEnrolledInvitationViolation,
    CompetitionFullViolation,
    DuplicateInvitationViolation,
    InvalidInvitationStatusViolation,
    InvitationCompetitionStatusViolation,
    InvitationExpiredViolation,
    SelfInvitationViolation,
)
from src.modules.competition.domain.services.location_builder import InvalidCountryError
from src.modules.competition.domain.value_objects.location import InvalidLocationError
from src.modules.competition.domain.value_objects.stroke_play_setup import (
    StrokePlaySettingsError,
)

CODIGOS: dict[type[Exception], int] = {
    # 400 (#251): pedir equipos, capitanes, draft, sobres o la clasificación por equipos a un
    # torneo que no los tiene, o unos ajustes de stroke play sin sentido. Lo pueden lanzar
    # rutas que no lo esperan; sin esto serían un 500
    TournamentTypeError: status.HTTP_400_BAD_REQUEST,
    StrokePlaySettingsError: status.HTTP_400_BAD_REQUEST,
    # 400: la petición no tiene sentido para el estado o las reglas del juego
    AgendaNotEditableError: status.HTTP_400_BAD_REQUEST,
    CompetitionFullError: status.HTTP_400_BAD_REQUEST,
    CompetitionNotClosedError: status.HTTP_400_BAD_REQUEST,
    CompetitionNotDraftError: status.HTTP_400_BAD_REQUEST,
    CreateRoundDuplicateSessionError: status.HTTP_400_BAD_REQUEST,
    CreateRoundGolfCourseNotInCompetitionError: status.HTTP_400_BAD_REQUEST,
    DateOutOfRangeError: status.HTTP_400_BAD_REQUEST,
    DeclareWalkoverCompetitionNotInProgressError: status.HTTP_400_BAD_REQUEST,
    DirectEnrollPlayerCompetitionNotActiveError: status.HTTP_400_BAD_REQUEST,
    EnrollmentClosedError: status.HTTP_400_BAD_REQUEST,
    EnrollmentStateError: status.HTTP_400_BAD_REQUEST,
    EnvelopesDecideThePairingsError: status.HTTP_400_BAD_REQUEST,
    EnvelopesNotRevealedError: status.HTTP_400_BAD_REQUEST,
    FranjaInvalidaError: status.HTTP_400_BAD_REQUEST,
    GolfCourseHasRoundsError: status.HTTP_400_BAD_REQUEST,
    GolfCourseNotAssignedError: status.HTTP_400_BAD_REQUEST,
    HandicapEditNotAllowedError: status.HTTP_400_BAD_REQUEST,
    InvalidActionError: status.HTTP_400_BAD_REQUEST,
    InvalidCountryError: status.HTTP_400_BAD_REQUEST,
    InvalidHoleNumberError: status.HTTP_400_BAD_REQUEST,
    InvalidLocationError: status.HTTP_400_BAD_REQUEST,
    InvalidReorderError: status.HTTP_400_BAD_REQUEST,
    InvalidTeeColorError: status.HTTP_400_BAD_REQUEST,
    InvalidWalkoverError: status.HTTP_400_BAD_REQUEST,
    MatchNotScheduledError: status.HTTP_400_BAD_REQUEST,
    NoGolfCoursesError: status.HTTP_400_BAD_REQUEST,
    NoTeamAssignmentError: status.HTTP_400_BAD_REQUEST,
    NothingToResetError: status.HTTP_400_BAD_REQUEST,
    PerfilIncompletoError: status.HTTP_400_BAD_REQUEST,
    PlayerNotEnrolledError: status.HTTP_400_BAD_REQUEST,
    PlayerNotInTeamError: status.HTTP_400_BAD_REQUEST,
    PlazaEnFranjaError: status.HTTP_400_BAD_REQUEST,
    RequestEnrollmentCompetitionNotActiveError: status.HTTP_400_BAD_REQUEST,
    RoundNotModifiableError: status.HTTP_400_BAD_REQUEST,
    RoundNotPendingMatchesError: status.HTTP_400_BAD_REQUEST,
    ScheduleAlreadyInPlayError: status.HTTP_400_BAD_REQUEST,
    ScorecardAlreadySubmittedError: status.HTTP_400_BAD_REQUEST,
    ScorecardNotReadyError: status.HTTP_400_BAD_REQUEST,
    SelfInvitationViolation: status.HTTP_400_BAD_REQUEST,
    SessionAlreadyPlayedError: status.HTTP_400_BAD_REQUEST,
    TeeColorNotFoundError: status.HTTP_400_BAD_REQUEST,
    TooManyEnrollmentsError: status.HTTP_400_BAD_REQUEST,
    UpdateMatchStatusCompetitionNotInProgressError: status.HTTP_400_BAD_REQUEST,
    UpdateRoundDuplicateSessionError: status.HTTP_400_BAD_REQUEST,
    UpdateRoundGolfCourseNotInCompetitionError: status.HTTP_400_BAD_REQUEST,
    WrongNumberOfPlayersError: status.HTTP_400_BAD_REQUEST,
    # 403: quien pide no puede hacerlo
    CancelEnrollmentNotOwnerError: status.HTTP_403_FORBIDDEN,
    CompetitionIsPrivateError: status.HTTP_403_FORBIDDEN,
    NotATeamCaptainError: status.HTTP_403_FORBIDDEN,
    NotCaptainOrCreatorError: status.HTTP_403_FORBIDDEN,
    NotCompetitionCreatorError: status.HTTP_403_FORBIDDEN,
    NotCompetitionParticipantError: status.HTTP_403_FORBIDDEN,
    NotCreatorError: status.HTTP_403_FORBIDDEN,
    NotInviteeError: status.HTTP_403_FORBIDDEN,
    NotMatchPlayerError: status.HTTP_403_FORBIDDEN,
    SetNamePreferenceNotOwnerError: status.HTTP_403_FORBIDDEN,
    WithdrawEnrollmentNotOwnerError: status.HTTP_403_FORBIDDEN,
    # 404: no existe (o no se le deja ver)
    CompetitionNotFoundError: status.HTTP_404_NOT_FOUND,
    EnrollmentNotFoundError: status.HTTP_404_NOT_FOUND,
    GolfCourseNotFoundError: status.HTTP_404_NOT_FOUND,
    InvitationNotFoundError: status.HTTP_404_NOT_FOUND,
    InviteeNotFoundError: status.HTTP_404_NOT_FOUND,
    MatchNotFoundError: status.HTTP_404_NOT_FOUND,
    PartidaNotFoundError: status.HTTP_404_NOT_FOUND,
    RoundNotFoundError: status.HTTP_404_NOT_FOUND,
    # 409: choca con lo que ya hay
    AlreadyEnrolledInvitationViolation: status.HTTP_409_CONFLICT,
    CompetitionAlreadyExistsError: status.HTTP_409_CONFLICT,
    DirectEnrollPlayerAlreadyEnrolledError: status.HTTP_409_CONFLICT,
    DuplicateInvitationViolation: status.HTTP_409_CONFLICT,
    EarlyRevealNeedsBothCaptainsError: status.HTTP_409_CONFLICT,
    InvalidInvitationStatusViolation: status.HTTP_409_CONFLICT,
    InvitationExpiredViolation: status.HTTP_409_CONFLICT,
    MatchNotScoringError: status.HTTP_409_CONFLICT,
    NotYourTurnError: status.HTTP_409_CONFLICT,
    RequestEnrollmentAlreadyEnrolledError: status.HTTP_409_CONFLICT,
    # 422: datos que no se pueden procesar
    CompetitionFullViolation: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InvitationCompetitionStatusViolation: status.HTTP_422_UNPROCESSABLE_CONTENT,
}
