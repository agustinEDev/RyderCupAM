"""
Tests unitarios para CompetitionPolicy - Domain service con reglas de negocio.

Valida business logic guards para prevenir abuso de lógica de negocio.
OWASP A04: Insecure Design (business logic abuse prevention)
"""

from datetime import date, timedelta

import pytest

from src.modules.competition.domain.services.competition_policy import (
    MAX_COMPETITIONS_PER_CREATOR,
    MAX_COMPETITION_DURATION_DAYS,
    MAX_ENROLLMENTS_PER_USER,
    CompetitionPolicy,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.exceptions.business_rule_violation import BusinessRuleViolation


# ======================================================================================
# TESTS: can_create_competition
# ======================================================================================


def test_can_create_competition_allows_when_under_limit():
    """
    Given: User with 49 existing competitions (under limit)
    When: Attempting to create a new competition
    Then: No exception raised (allowed)
    """
    user_id = UserId.generate()
    existing_count = MAX_COMPETITIONS_PER_CREATOR - 1

    # Should not raise
    CompetitionPolicy.can_create_competition(user_id, existing_count)


def test_can_create_competition_rejects_when_at_limit():
    """
    Given: User with 50 existing competitions (at limit)
    When: Attempting to create a new competition
    Then: BusinessRuleViolation raised
    """
    user_id = UserId.generate()
    existing_count = MAX_COMPETITIONS_PER_CREATOR

    with pytest.raises(BusinessRuleViolation) as exc_info:
        CompetitionPolicy.can_create_competition(user_id, existing_count)

    assert "cannot create more than" in str(exc_info.value).lower()
    assert str(MAX_COMPETITIONS_PER_CREATOR) in str(exc_info.value)


def test_can_create_competition_rejects_when_over_limit():
    """
    Given: User with 100 existing competitions (way over limit)
    When: Attempting to create a new competition
    Then: BusinessRuleViolation raised
    """
    user_id = UserId.generate()
    existing_count = 100

    with pytest.raises(BusinessRuleViolation):
        CompetitionPolicy.can_create_competition(user_id, existing_count)


def test_can_create_competition_allows_when_zero():
    """
    Given: User with 0 existing competitions
    When: Attempting to create first competition
    Then: No exception raised (allowed)
    """
    user_id = UserId.generate()
    existing_count = 0

    # Should not raise
    CompetitionPolicy.can_create_competition(user_id, existing_count)


# ======================================================================================
# TESTS: can_enroll
# ======================================================================================


def test_can_enroll_allows_when_valid():
    """
    Given: Valid enrollment request (no duplicate, under limit, active competition)
    When: Attempting to enroll
    Then: No exception raised (allowed)
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()
    start_date = date.today() + timedelta(days=7)

    # Should not raise
    CompetitionPolicy.can_enroll(
        user_id=user_id,
        competition_id=competition_id,
        existing_enrollment_id=None,
        competition_status=CompetitionStatus.ACTIVE,
        competition_start_date=start_date,
        user_total_enrollments=5,
    )


def test_can_enroll_rejects_duplicate_enrollment():
    """
    Given: User already enrolled in competition
    When: Attempting to enroll again
    Then: BusinessRuleViolation raised (duplicate prevention)
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()
    existing_enrollment_id = "existing-uuid"
    start_date = date.today() + timedelta(days=7)

    with pytest.raises(BusinessRuleViolation) as exc_info:
        CompetitionPolicy.can_enroll(
            user_id=user_id,
            competition_id=competition_id,
            existing_enrollment_id=existing_enrollment_id,
            competition_status=CompetitionStatus.ACTIVE,
            competition_start_date=start_date,
            user_total_enrollments=5,
        )

    assert "already enrolled" in str(exc_info.value).lower()


def test_can_enroll_rejects_when_user_at_enrollment_limit():
    """
    Given: User with 20 active enrollments (at limit)
    When: Attempting to enroll in new competition
    Then: BusinessRuleViolation raised
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()
    start_date = date.today() + timedelta(days=7)

    with pytest.raises(BusinessRuleViolation) as exc_info:
        CompetitionPolicy.can_enroll(
            user_id=user_id,
            competition_id=competition_id,
            existing_enrollment_id=None,
            competition_status=CompetitionStatus.ACTIVE,
            competition_start_date=start_date,
            user_total_enrollments=MAX_ENROLLMENTS_PER_USER,
        )

    assert "cannot enroll in more than" in str(exc_info.value).lower()
    assert str(MAX_ENROLLMENTS_PER_USER) in str(exc_info.value)


def test_can_enroll_rejects_when_competition_in_draft():
    """
    Given: Competition in DRAFT status
    When: Attempting to enroll
    Then: BusinessRuleViolation raised (only ACTIVE/CLOSED allowed)
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()
    start_date = date.today() + timedelta(days=7)

    with pytest.raises(BusinessRuleViolation) as exc_info:
        CompetitionPolicy.can_enroll(
            user_id=user_id,
            competition_id=competition_id,
            existing_enrollment_id=None,
            competition_status=CompetitionStatus.DRAFT,
            competition_start_date=start_date,
            user_total_enrollments=5,
        )

    assert "enrollments only allowed" in str(exc_info.value).lower()


def test_can_enroll_rejects_when_competition_completed():
    """
    Given: Competition in COMPLETED status
    When: Attempting to enroll
    Then: BusinessRuleViolation raised
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()
    start_date = date.today() - timedelta(days=7)  # Past date

    with pytest.raises(BusinessRuleViolation):
        CompetitionPolicy.can_enroll(
            user_id=user_id,
            competition_id=competition_id,
            existing_enrollment_id=None,
            competition_status=CompetitionStatus.COMPLETED,
            competition_start_date=start_date,
            user_total_enrollments=5,
        )


def test_can_enroll_rejects_when_competition_already_started():
    """
    Given: Competition that already started (start_date is today or past)
    When: Attempting to enroll
    Then: BusinessRuleViolation raised (temporal constraint)
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()
    start_date = date.today()  # Today (already started)

    with pytest.raises(BusinessRuleViolation) as exc_info:
        CompetitionPolicy.can_enroll(
            user_id=user_id,
            competition_id=competition_id,
            existing_enrollment_id=None,
            competition_status=CompetitionStatus.ACTIVE,
            competition_start_date=start_date,
            user_total_enrollments=5,
        )

    assert "cannot enroll after start date" in str(exc_info.value).lower()


def test_can_enroll_allows_when_competition_status_closed():
    """
    Given: Competition in CLOSED status (but not started yet)
    When: Attempting to enroll
    Then: No exception raised (CLOSED is allowed for direct enrollments)
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()
    start_date = date.today() + timedelta(days=7)

    # Should not raise
    CompetitionPolicy.can_enroll(
        user_id=user_id,
        competition_id=competition_id,
        existing_enrollment_id=None,
        competition_status=CompetitionStatus.CLOSED,
        competition_start_date=start_date,
        user_total_enrollments=5,
    )


# ======================================================================================
# TESTS: validate_capacity
# ======================================================================================


def test_validate_capacity_allows_when_under_limit():
    """
    Given: Competition with 23/24 players
    When: Validating capacity
    Then: No exception raised (space available)
    """
    competition_id = CompetitionId.generate()

    # Should not raise
    CompetitionPolicy.validate_capacity(
        current_enrollments=23, max_players=24, competition_id=competition_id
    )


def test_validate_capacity_rejects_when_at_limit():
    """
    Given: Competition with 24/24 players (full)
    When: Validating capacity
    Then: BusinessRuleViolation raised
    """
    competition_id = CompetitionId.generate()

    with pytest.raises(BusinessRuleViolation) as exc_info:
        CompetitionPolicy.validate_capacity(
            current_enrollments=24, max_players=24, competition_id=competition_id
        )

    assert "maximum capacity" in str(exc_info.value).lower()


def test_validate_capacity_rejects_when_over_limit():
    """
    Given: Competition with 30/24 players (over limit - edge case)
    When: Validating capacity
    Then: BusinessRuleViolation raised
    """
    competition_id = CompetitionId.generate()

    with pytest.raises(BusinessRuleViolation):
        CompetitionPolicy.validate_capacity(
            current_enrollments=30, max_players=24, competition_id=competition_id
        )


def test_validate_capacity_allows_when_empty():
    """
    Given: Competition with 0/24 players
    When: Validating capacity
    Then: No exception raised
    """
    competition_id = CompetitionId.generate()

    # Should not raise
    CompetitionPolicy.validate_capacity(
        current_enrollments=0, max_players=24, competition_id=competition_id
    )


# ======================================================================================
# TESTS: validate_date_range
# ======================================================================================


def test_validate_date_range_allows_when_valid():
    """
    Given: Valid date range (start before end, reasonable duration)
    When: Validating date range
    Then: No exception raised
    """
    start_date = date(2026, 6, 1)
    end_date = date(2026, 6, 3)

    # Should not raise
    CompetitionPolicy.validate_date_range(start_date, end_date, "Test Competition")


def test_validate_date_range_rejects_when_start_after_end():
    """
    Given: Start date after end date (invalid order)
    When: Validating date range
    Then: BusinessRuleViolation raised
    """
    start_date = date(2026, 6, 10)
    end_date = date(2026, 6, 5)

    with pytest.raises(BusinessRuleViolation) as exc_info:
        CompetitionPolicy.validate_date_range(start_date, end_date, "Test")

    assert "must be before end date" in str(exc_info.value).lower()


def test_validate_date_range_rejects_when_start_equals_end():
    """
    Given: Start date equals end date (zero duration)
    When: Validating date range
    Then: BusinessRuleViolation raised
    """
    same_date = date(2026, 6, 10)

    with pytest.raises(BusinessRuleViolation):
        CompetitionPolicy.validate_date_range(same_date, same_date, "Test")


def test_validate_date_range_rejects_when_duration_exceeds_limit():
    """
    Given: Competition duration of 366 days (over limit)
    When: Validating date range
    Then: BusinessRuleViolation raised
    """
    start_date = date(2026, 6, 1)
    end_date = start_date + timedelta(days=MAX_COMPETITION_DURATION_DAYS + 1)

    with pytest.raises(BusinessRuleViolation) as exc_info:
        CompetitionPolicy.validate_date_range(start_date, end_date, "Test")

    assert "exceeds maximum allowed" in str(exc_info.value).lower()


def test_validate_date_range_allows_when_duration_at_limit():
    """
    Given: Competition duration of exactly 365 days (at limit)
    When: Validating date range
    Then: No exception raised
    """
    start_date = date(2026, 6, 1)
    end_date = start_date + timedelta(days=MAX_COMPETITION_DURATION_DAYS)

    # Should not raise
    CompetitionPolicy.validate_date_range(start_date, end_date, "Test")


