# -*- coding: utf-8 -*-
"""Competition Application Use Cases."""

from .create_competition_use_case import (
    CreateCompetitionUseCase,
    CompetitionAlreadyExistsError,
)
from .update_competition_use_case import (
    UpdateCompetitionUseCase,
    NotCompetitionCreatorError,
    CompetitionNotEditableError,
)
from .get_competition_use_case import (
    GetCompetitionUseCase,
    CompetitionNotFoundError,
)
from .delete_competition_use_case import (
    DeleteCompetitionUseCase,
    CompetitionNotDeletableError,
)
from .activate_competition_use_case import (
    ActivateCompetitionUseCase,
)
from .close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from .start_competition_use_case import (
    StartCompetitionUseCase,
)
from .complete_competition_use_case import (
    CompleteCompetitionUseCase,
)
from .cancel_competition_use_case import (
    CancelCompetitionUseCase,
)

__all__ = [
    # CRUD Operations
    "CreateCompetitionUseCase",
    "UpdateCompetitionUseCase",
    "GetCompetitionUseCase",
    "DeleteCompetitionUseCase",
    # State Transitions
    "ActivateCompetitionUseCase",
    "CloseEnrollmentsUseCase",
    "StartCompetitionUseCase",
    "CompleteCompetitionUseCase",
    "CancelCompetitionUseCase",
    # Exceptions
    "CompetitionAlreadyExistsError",
    "CompetitionNotFoundError",
    "NotCompetitionCreatorError",
    "CompetitionNotEditableError",
    "CompetitionNotDeletableError",
]
