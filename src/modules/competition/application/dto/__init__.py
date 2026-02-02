"""Competition application DTOs."""

from .competition_dto import (
    # Lifecycle Transitions
    ActivateCompetitionRequestDTO,
    ActivateCompetitionResponseDTO,
    # Golf Course Management
    AddGolfCourseBodyDTO,
    AddGolfCourseRequestDTO,
    AddGolfCourseResponseDTO,
    CancelCompetitionRequestDTO,
    CancelCompetitionResponseDTO,
    CloseEnrollmentsRequestDTO,
    CloseEnrollmentsResponseDTO,
    CompetitionGolfCourseResponseDTO,
    CompetitionResponseDTO,
    CompleteCompetitionRequestDTO,
    CompleteCompetitionResponseDTO,
    # Create & Update
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
    # Delete & Cancel
    DeleteCompetitionRequestDTO,
    DeleteCompetitionResponseDTO,
    GolfCourseDetailDTO,
    HoleResponseDTO,
    RemoveGolfCourseRequestDTO,
    RemoveGolfCourseResponseDTO,
    ReorderGolfCourseIdsRequest,
    ReorderGolfCoursesRequestDTO,
    ReorderGolfCoursesResponseDTO,
    StartCompetitionRequestDTO,
    StartCompetitionResponseDTO,
    TeeResponseDTO,
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
    "AddGolfCourseBodyDTO",
    "AddGolfCourseRequestDTO",
    "AddGolfCourseResponseDTO",
    "CancelCompetitionRequestDTO",
    "CancelCompetitionResponseDTO",
    "CancelEnrollmentRequestDTO",
    "CancelEnrollmentResponseDTO",
    "CloseEnrollmentsRequestDTO",
    "CloseEnrollmentsResponseDTO",
    "CompetitionGolfCourseResponseDTO",
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
    "GolfCourseDetailDTO",
    "HandleEnrollmentRequestDTO",
    "HandleEnrollmentResponseDTO",
    "HoleResponseDTO",
    "RemoveGolfCourseRequestDTO",
    "RemoveGolfCourseResponseDTO",
    "ReorderGolfCourseIdsRequest",
    "ReorderGolfCoursesRequestDTO",
    "ReorderGolfCoursesResponseDTO",
    # Enrollment DTOs
    "RequestEnrollmentRequestDTO",
    "RequestEnrollmentResponseDTO",
    "SetCustomHandicapRequestDTO",
    "SetCustomHandicapResponseDTO",
    "StartCompetitionRequestDTO",
    "StartCompetitionResponseDTO",
    "TeeResponseDTO",
    "UpdateCompetitionRequestDTO",
    "UpdateCompetitionResponseDTO",
    "WithdrawEnrollmentRequestDTO",
    "WithdrawEnrollmentResponseDTO",
]
