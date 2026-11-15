"""Tests para Enrollment DTOs."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.competition.application.dto.enrollment_dto import (
    HandleEnrollmentRequestDTO,
    RequestEnrollmentRequestDTO,
    SetCustomHandicapRequestDTO,
)


class TestRequestEnrollmentRequestDTO:
    """Tests para RequestEnrollmentRequestDTO."""

    def test_create_with_valid_data(self):
        """Debe crear DTO con datos válidos."""
        competition_id = uuid4()
        user_id = uuid4()

        dto = RequestEnrollmentRequestDTO(competition_id=competition_id, user_id=user_id)

        assert dto.competition_id == competition_id
        assert dto.user_id == user_id


class TestHandleEnrollmentRequestDTO:
    """Tests para HandleEnrollmentRequestDTO."""

    def test_create_with_approve_action(self):
        """Debe crear DTO con acción APPROVE."""
        dto = HandleEnrollmentRequestDTO(enrollment_id=uuid4(), action="APPROVE")

        assert dto.action == "APPROVE"

    def test_create_with_reject_action(self):
        """Debe crear DTO con acción REJECT."""
        dto = HandleEnrollmentRequestDTO(enrollment_id=uuid4(), action="REJECT")

        assert dto.action == "REJECT"

    def test_uppercase_action(self):
        """Debe convertir action a mayúsculas."""
        dto = HandleEnrollmentRequestDTO(enrollment_id=uuid4(), action="approve")

        assert dto.action == "APPROVE"

    def test_invalid_action(self):
        """Debe rechazar acción inválida."""
        with pytest.raises(ValueError, match="action debe ser"):
            HandleEnrollmentRequestDTO(enrollment_id=uuid4(), action="INVALID")


class TestSetCustomHandicapRequestDTO:
    """Tests para SetCustomHandicapRequestDTO."""

    def test_create_with_valid_handicap(self):
        """Debe crear DTO con hándicap válido."""
        dto = SetCustomHandicapRequestDTO(enrollment_id=uuid4(), custom_handicap=Decimal("20.5"))

        assert dto.custom_handicap == Decimal("20.5")

    def test_handicap_below_minimum(self):
        """Debe rechazar hándicap menor a -10.0."""
        with pytest.raises(ValidationError):
            SetCustomHandicapRequestDTO(enrollment_id=uuid4(), custom_handicap=Decimal("-11.0"))

    def test_handicap_above_maximum(self):
        """Debe rechazar hándicap mayor a 54.0."""
        with pytest.raises(ValidationError):
            SetCustomHandicapRequestDTO(enrollment_id=uuid4(), custom_handicap=Decimal("55.0"))

    def test_handicap_at_boundaries(self):
        """Debe aceptar hándicap en los límites."""
        dto_min = SetCustomHandicapRequestDTO(
            enrollment_id=uuid4(), custom_handicap=Decimal("-10.0")
        )
        dto_max = SetCustomHandicapRequestDTO(
            enrollment_id=uuid4(), custom_handicap=Decimal("54.0")
        )

        assert dto_min.custom_handicap == Decimal("-10.0")
        assert dto_max.custom_handicap == Decimal("54.0")
