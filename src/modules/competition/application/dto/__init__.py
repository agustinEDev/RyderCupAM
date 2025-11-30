"""Competition application DTOs."""

from .competition_dto import (
    # Lifecycle Transitions
    ActivateCompetitionRequestDTO,
    ActivateCompetitionResponseDTO,
    CancelCompetitionRequestDTO,
    CancelCompetitionResponseDTO,
    CloseEnrollmentsRequestDTO,
    CloseEnrollmentsResponseDTO,
    CompetitionResponseDTO,
    CompleteCompetitionRequestDTO,
    CompleteCompetitionResponseDTO,
    # Create & Update
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
    # Delete & Cancel
    DeleteCompetitionRequestDTO,
    DeleteCompetitionResponseDTO,
    StartCompetitionRequestDTO,
    StartCompetitionResponseDTO,
    UpdateCompetitionRequestDTO,
    UpdateCompetitionResponseDTO,
)
from .enrollment_dto import (
    # Cancel & Withdraw
    CancelEnrollmentRequestDTO,
    CancelEnrollmentResponseDTO,
    # Direct Enroll
    DirectEnrollPlayerRequestDTO,
    DirectEnrollPlayerResponseDTO,
    # Generic
    EnrollmentResponseDTO,
    # Handle Enrollment
    HandleEnrollmentRequestDTO,
    HandleEnrollmentResponseDTO,
    # Request Enrollment
    RequestEnrollmentRequestDTO,
    RequestEnrollmentResponseDTO,
    # Custom Handicap
    SetCustomHandicapRequestDTO,
    SetCustomHandicapResponseDTO,
    WithdrawEnrollmentRequestDTO,
    WithdrawEnrollmentResponseDTO,
)

__all__ = [
    "ActivateCompetitionRequestDTO",
    "ActivateCompetitionResponseDTO",
    "CancelCompetitionRequestDTO",
    "CancelCompetitionResponseDTO",
    "CancelEnrollmentRequestDTO",
    "CancelEnrollmentResponseDTO",
    "CloseEnrollmentsRequestDTO",
    "CloseEnrollmentsResponseDTO",
    "CompetitionResponseDTO",
    "CompleteCompetitionRequestDTO",
    "CompleteCompetitionResponseDTO",
    # Competition DTOs
    "CreateCompetitionRequestDTO",
    "CreateCompetitionResponseDTO",
    "DeleteCompetitionRequestDTO",
    "DeleteCompetitionResponseDTO",
    "DirectEnrollPlayerRequestDTO",
    "DirectEnrollPlayerResponseDTO",
    "EnrollmentResponseDTO",
    "HandleEnrollmentRequestDTO",
    "HandleEnrollmentResponseDTO",
    # Enrollment DTOs
    "RequestEnrollmentRequestDTO",
    "RequestEnrollmentResponseDTO",
    "SetCustomHandicapRequestDTO",
    "SetCustomHandicapResponseDTO",
    "StartCompetitionRequestDTO",
    "StartCompetitionResponseDTO",
    "UpdateCompetitionRequestDTO",
    "UpdateCompetitionResponseDTO",
    "WithdrawEnrollmentRequestDTO",
    "WithdrawEnrollmentResponseDTO",
]
