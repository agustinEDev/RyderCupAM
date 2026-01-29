"""
Tests unitarios para authorization helpers (RBAC).

Valida las funciones de autorización que determinan permisos de usuarios
según el modelo de roles contextual del sistema.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.competition.domain.value_objects.handicap_settings import (
    HandicapSettings,
    HandicapType,
)
from src.modules.competition.domain.value_objects.location import Location
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.infrastructure.security.authorization import (
    can_modify_competition,
    is_admin,
    is_creator_of,
    is_player_in,
    require_admin,
    require_creator_or_admin,
    require_player_in_competition,
)

# ======================================================================================
# FIXTURES
# ======================================================================================


@pytest.fixture
def admin_user():
    """Usuario con privilegios de administrador."""
    return UserResponseDTO(
        id=uuid4(),
        email="admin@rydercupfriends.com",
        first_name="Admin",
        last_name="User",
        country_code="ES",
        handicap=15.0,
        handicap_updated_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        email_verified=True,
        is_admin=True,  # ← Admin flag
    )


@pytest.fixture
def creator_user():
    """Usuario creador (no admin)."""
    return UserResponseDTO(
        id=uuid4(),
        email="creator@example.com",
        first_name="Creator",
        last_name="User",
        country_code="ES",
        handicap=12.0,
        handicap_updated_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        email_verified=True,
        is_admin=False,
    )


@pytest.fixture
def regular_user():
    """Usuario regular (no admin, no creator)."""
    return UserResponseDTO(
        id=uuid4(),
        email="player@example.com",
        first_name="Regular",
        last_name="User",
        country_code="ES",
        handicap=18.0,
        handicap_updated_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        email_verified=True,
        is_admin=False,
    )


@pytest.fixture
def competition(creator_user):
    """Competición creada por creator_user."""
    return Competition(
        id=CompetitionId.generate(),
        creator_id=UserId(str(creator_user.id)),
        name=CompetitionName("Ryder Cup Madrid 2026"),
        dates=DateRange(date(2026, 6, 1), date(2026, 6, 3)),
        location=Location(CountryCode("ES")),
        team_1_name="Europe",
        team_2_name="USA",
        handicap_settings=HandicapSettings(HandicapType.PERCENTAGE, 90),
        max_players=24,
        status=CompetitionStatus.DRAFT,
    )


# ======================================================================================
# TESTS: is_admin()
# ======================================================================================


def test_is_admin_returns_true_for_admin_user(admin_user):
    """
    Given: Un usuario con is_admin=True
    When: Se llama a is_admin()
    Then: Retorna True
    """
    assert is_admin(admin_user) is True


def test_is_admin_returns_false_for_regular_user(regular_user):
    """
    Given: Un usuario con is_admin=False
    When: Se llama a is_admin()
    Then: Retorna False
    """
    assert is_admin(regular_user) is False


# ======================================================================================
# TESTS: is_creator_of()
# ======================================================================================


def test_is_creator_of_returns_true_when_user_is_creator(creator_user, competition):
    """
    Given: Un usuario que creó la competición
    When: Se llama a is_creator_of()
    Then: Retorna True
    """
    assert is_creator_of(creator_user, competition) is True


def test_is_creator_of_returns_false_when_user_is_not_creator(regular_user, competition):
    """
    Given: Un usuario que NO creó la competición
    When: Se llama a is_creator_of()
    Then: Retorna False
    """
    assert is_creator_of(regular_user, competition) is False


# ======================================================================================
# TESTS: can_modify_competition()
# ======================================================================================


def test_can_modify_competition_returns_true_for_admin(admin_user, competition):
    """
    Given: Un usuario admin (aunque no sea creator)
    When: Se llama a can_modify_competition()
    Then: Retorna True (admin override)
    """
    assert can_modify_competition(admin_user, competition) is True


def test_can_modify_competition_returns_true_for_creator(creator_user, competition):
    """
    Given: Un usuario creador (aunque no sea admin)
    When: Se llama a can_modify_competition()
    Then: Retorna True
    """
    assert can_modify_competition(creator_user, competition) is True


def test_can_modify_competition_returns_false_for_unauthorized_user(regular_user, competition):
    """
    Given: Un usuario que NO es admin NI creator
    When: Se llama a can_modify_competition()
    Then: Retorna False
    """
    assert can_modify_competition(regular_user, competition) is False


# ======================================================================================
# TESTS: require_admin()
# ======================================================================================


def test_require_admin_succeeds_for_admin_user(admin_user):
    """
    Given: Un usuario admin
    When: Se llama a require_admin()
    Then: No lanza excepción (éxito silencioso)
    """
    require_admin(admin_user)  # No debe lanzar excepción


def test_require_admin_raises_403_for_non_admin_user(regular_user):
    """
    Given: Un usuario NO admin
    When: Se llama a require_admin()
    Then: Lanza HTTPException 403 Forbidden
    """
    with pytest.raises(HTTPException) as exc_info:
        require_admin(regular_user)

    assert exc_info.value.status_code == 403
    assert "administrator privileges" in exc_info.value.detail.lower()


# ======================================================================================
# TESTS: require_creator_or_admin()
# ======================================================================================


def test_require_creator_or_admin_succeeds_for_admin(admin_user, competition):
    """
    Given: Un usuario admin
    When: Se llama a require_creator_or_admin()
    Then: No lanza excepción (admin override)
    """
    require_creator_or_admin(admin_user, competition)


def test_require_creator_or_admin_succeeds_for_creator(creator_user, competition):
    """
    Given: Un usuario creador
    When: Se llama a require_creator_or_admin()
    Then: No lanza excepción
    """
    require_creator_or_admin(creator_user, competition)


def test_require_creator_or_admin_raises_403_for_unauthorized_user(regular_user, competition):
    """
    Given: Un usuario NO admin NI creator
    When: Se llama a require_creator_or_admin()
    Then: Lanza HTTPException 403 Forbidden
    """
    with pytest.raises(HTTPException) as exc_info:
        require_creator_or_admin(regular_user, competition)

    assert exc_info.value.status_code == 403
    assert "creator or an administrator" in exc_info.value.detail.lower()


# ======================================================================================
# TESTS: is_player_in() - Async con Mock UoW
# ======================================================================================


@pytest.mark.asyncio
async def test_is_player_in_returns_true_when_user_is_enrolled_with_approved_status():
    """
    Given: Un usuario con enrollment APPROVED en una competición
    When: Se llama a is_player_in()
    Then: Retorna True
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()

    # Mock enrollment APPROVED
    enrollment = Enrollment(
        id=EnrollmentId.generate(),
        competition_id=competition_id,
        user_id=user_id,
        status=EnrollmentStatus.APPROVED,
    )

    # Mock UoW
    mock_uow = Mock()
    mock_uow.enrollments.find_by_user_and_competition = AsyncMock(return_value=enrollment)

    result = await is_player_in(user_id, competition_id, mock_uow)
    assert result is True


@pytest.mark.asyncio
async def test_is_player_in_returns_false_when_user_is_not_enrolled():
    """
    Given: Un usuario SIN enrollment en una competición
    When: Se llama a is_player_in()
    Then: Retorna False
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()

    # Mock UoW - no enrollment
    mock_uow = Mock()
    mock_uow.enrollments.find_by_user_and_competition = AsyncMock(return_value=None)

    result = await is_player_in(user_id, competition_id, mock_uow)
    assert result is False


@pytest.mark.asyncio
async def test_is_player_in_returns_false_when_enrollment_is_not_approved():
    """
    Given: Un usuario con enrollment REJECTED (o cualquier otro status != APPROVED)
    When: Se llama a is_player_in()
    Then: Retorna False
    """
    user_id = UserId.generate()
    competition_id = CompetitionId.generate()

    # Mock enrollment REJECTED
    enrollment = Enrollment(
        id=EnrollmentId.generate(),
        competition_id=competition_id,
        user_id=user_id,
        status=EnrollmentStatus.REJECTED,
    )

    # Mock UoW
    mock_uow = Mock()
    mock_uow.enrollments.find_by_user_and_competition = AsyncMock(return_value=enrollment)

    result = await is_player_in(user_id, competition_id, mock_uow)
    assert result is False


# ======================================================================================
# TESTS: require_player_in_competition() - Async con Mock UoW
# ======================================================================================


@pytest.mark.asyncio
async def test_require_player_in_competition_succeeds_when_user_is_player(regular_user):
    """
    Given: Un usuario con enrollment APPROVED
    When: Se llama a require_player_in_competition()
    Then: No lanza excepción
    """
    competition_id = CompetitionId.generate()
    user_id = UserId(str(regular_user.id))

    # Mock enrollment APPROVED
    enrollment = Enrollment(
        id=EnrollmentId.generate(),
        competition_id=competition_id,
        user_id=user_id,
        status=EnrollmentStatus.APPROVED,
    )

    # Mock UoW
    mock_uow = Mock()
    mock_uow.enrollments.find_by_user_and_competition = AsyncMock(return_value=enrollment)

    # No debe lanzar excepción
    await require_player_in_competition(regular_user, competition_id, mock_uow)


@pytest.mark.asyncio
async def test_require_player_in_competition_raises_403_when_user_is_not_player(regular_user):
    """
    Given: Un usuario SIN enrollment APPROVED
    When: Se llama a require_player_in_competition()
    Then: Lanza HTTPException 403 Forbidden
    """
    competition_id = CompetitionId.generate()

    # Mock UoW - no enrollment
    mock_uow = Mock()
    mock_uow.enrollments.find_by_user_and_competition = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await require_player_in_competition(regular_user, competition_id, mock_uow)

    assert exc_info.value.status_code == 403
    assert "enrolled players" in exc_info.value.detail.lower()
