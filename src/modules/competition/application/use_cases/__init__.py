"""Competition Application Use Cases."""

from .activate_competition_use_case import (
    ActivateCompetitionUseCase,
)
from .add_golf_course_use_case import (
    AddGolfCourseToCompetitionUseCase,
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
from .create_competition_use_case import (
    CompetitionAlreadyExistsError,
    CreateCompetitionUseCase,
)
from .delete_competition_use_case import (
    CompetitionNotDeletableError,
    DeleteCompetitionUseCase,
)
from .get_competition_use_case import (
    CompetitionNotFoundError,
    GetCompetitionUseCase,
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

__all__ = [
    # State Transitions
    "ActivateCompetitionUseCase",
    "AddGolfCourseToCompetitionUseCase",
    "CancelCompetitionUseCase",
    "CloseEnrollmentsUseCase",
    # Exceptions
    "CompetitionAlreadyExistsError",
    "CompetitionNotDeletableError",
    "CompetitionNotEditableError",
    "CompetitionNotFoundError",
    "CompleteCompetitionUseCase",
    # CRUD Operations
    "CreateCompetitionUseCase",
    "DeleteCompetitionUseCase",
    "GetCompetitionUseCase",
    "NotCompetitionCreatorError",
    "RemoveGolfCourseFromCompetitionUseCase",
    "ReorderGolfCoursesUseCase",
    "StartCompetitionUseCase",
    "UpdateCompetitionUseCase",
]
