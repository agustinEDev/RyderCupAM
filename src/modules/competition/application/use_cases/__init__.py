"""Competition Application Use Cases."""

from .activate_competition_use_case import (
    ActivateCompetitionUseCase,
)
from .add_golf_course_use_case import (
    AddGolfCourseToCompetitionUseCase,
)
from .assign_teams_use_case import (
    AssignTeamsUseCase,
)
from .cancel_competition_use_case import (
    CancelCompetitionUseCase,
)
from .close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from .complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
from .configure_schedule_use_case import (
    ConfigureScheduleUseCase,
)
from .create_competition_use_case import (
    CompetitionAlreadyExistsError,
    CreateCompetitionUseCase,
)
from .create_round_use_case import (
    CreateRoundUseCase,
)
from .declare_walkover_use_case import (
    DeclareWalkoverUseCase,
)
from .delete_competition_use_case import (
    CompetitionNotDeletableError,
    DeleteCompetitionUseCase,
)
from .delete_round_use_case import (
    DeleteRoundUseCase,
)
from .generate_matches_use_case import (
    GenerateMatchesUseCase,
)
from .get_competition_use_case import (
    CompetitionNotFoundError,
    GetCompetitionUseCase,
)
from .get_match_detail_use_case import (
    GetMatchDetailUseCase,
)
from .get_schedule_use_case import (
    GetScheduleUseCase,
)
from .reassign_match_players_use_case import (
    ReassignMatchPlayersUseCase,
)
from .remove_golf_course_use_case import (
    RemoveGolfCourseFromCompetitionUseCase,
)
from .reorder_golf_courses_use_case import (
    ReorderGolfCoursesUseCase,
)
from .start_competition_use_case import (
    StartCompetitionUseCase,
)
from .update_competition_use_case import (
    CompetitionNotEditableError,
    NotCompetitionCreatorError,
    UpdateCompetitionUseCase,
)
from .update_match_status_use_case import (
    UpdateMatchStatusUseCase,
)
from .update_round_use_case import (
    UpdateRoundUseCase,
)

__all__ = [
    # State Transitions
    "ActivateCompetitionUseCase",
    "AddGolfCourseToCompetitionUseCase",
    "AssignTeamsUseCase",
    "CancelCompetitionUseCase",
    "CloseEnrollmentsUseCase",
    # Exceptions
    "CompetitionAlreadyExistsError",
    "CompetitionNotDeletableError",
    "CompetitionNotEditableError",
    "CompetitionNotFoundError",
    "CompleteCompetitionUseCase",
    "ConfigureScheduleUseCase",
    # CRUD Operations
    "CreateCompetitionUseCase",
    "CreateRoundUseCase",
    "DeclareWalkoverUseCase",
    "DeleteCompetitionUseCase",
    "DeleteRoundUseCase",
    "GenerateMatchesUseCase",
    "GetCompetitionUseCase",
    "GetMatchDetailUseCase",
    "GetScheduleUseCase",
    "NotCompetitionCreatorError",
    "ReassignMatchPlayersUseCase",
    "RemoveGolfCourseFromCompetitionUseCase",
    "ReorderGolfCoursesUseCase",
    "StartCompetitionUseCase",
    "UpdateCompetitionUseCase",
    "UpdateMatchStatusUseCase",
    "UpdateRoundUseCase",
]
