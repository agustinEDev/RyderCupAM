# -*- coding: utf-8 -*-
"""Competition application DTOs."""

from .competition_dto import (
    # Create & Update
    CreateCompetitionRequestDTO,
    CreateCompetitionResponseDTO,
    UpdateCompetitionRequestDTO,
    UpdateCompetitionResponseDTO,
    CompetitionResponseDTO,
    # Lifecycle Transitions
    ActivateCompetitionRequestDTO,
    ActivateCompetitionResponseDTO,
    CloseEnrollmentsRequestDTO,
    CloseEnrollmentsResponseDTO,
    StartCompetitionRequestDTO,
    StartCompetitionResponseDTO,
    CompleteCompetitionRequestDTO,
    CompleteCompetitionResponseDTO,
    # Delete & Cancel
    DeleteCompetitionRequestDTO,
    DeleteCompetitionResponseDTO,
    CancelCompetitionRequestDTO,
    CancelCompetitionResponseDTO,
)

from .enrollment_dto import (
    # Request Enrollment
    RequestEnrollmentRequestDTO,
    RequestEnrollmentResponseDTO,
    # Direct Enroll
    DirectEnrollPlayerRequestDTO,
    DirectEnrollPlayerResponseDTO,
    # Handle Enrollment
    HandleEnrollmentRequestDTO,
    HandleEnrollmentResponseDTO,
    # Cancel & Withdraw
    CancelEnrollmentRequestDTO,
    CancelEnrollmentResponseDTO,
    WithdrawEnrollmentRequestDTO,
    WithdrawEnrollmentResponseDTO,
    # Custom Handicap
    SetCustomHandicapRequestDTO,
    SetCustomHandicapResponseDTO,
    # Generic
    EnrollmentResponseDTO,
)

__all__ = [
    # Competition DTOs
    "CreateCompetitionRequestDTO",
    "CreateCompetitionResponseDTO",
    "UpdateCompetitionRequestDTO",
    "UpdateCompetitionResponseDTO",
    "CompetitionResponseDTO",
    "ActivateCompetitionRequestDTO",
    "ActivateCompetitionResponseDTO",
    "CloseEnrollmentsRequestDTO",
    "CloseEnrollmentsResponseDTO",
    "StartCompetitionRequestDTO",
    "StartCompetitionResponseDTO",
    "CompleteCompetitionRequestDTO",
    "CompleteCompetitionResponseDTO",
    "DeleteCompetitionRequestDTO",
    "DeleteCompetitionResponseDTO",
    "CancelCompetitionRequestDTO",
    "CancelCompetitionResponseDTO",
    # Enrollment DTOs
    "RequestEnrollmentRequestDTO",
    "RequestEnrollmentResponseDTO",
    "DirectEnrollPlayerRequestDTO",
    "DirectEnrollPlayerResponseDTO",
    "HandleEnrollmentRequestDTO",
    "HandleEnrollmentResponseDTO",
    "CancelEnrollmentRequestDTO",
    "CancelEnrollmentResponseDTO",
    "WithdrawEnrollmentRequestDTO",
    "WithdrawEnrollmentResponseDTO",
    "SetCustomHandicapRequestDTO",
    "SetCustomHandicapResponseDTO",
    "EnrollmentResponseDTO",
]
