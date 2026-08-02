"""Tests para GetAdminStatsUseCase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.user.application.use_cases.get_admin_stats_use_case import (
    GetAdminStatsUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


def _make_uow_mock(**repo_attrs):
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    for name, repo in repo_attrs.items():
        setattr(uow, name, repo)
    return uow


class TestGetAdminStatsUseCase:
    @pytest.fixture
    def user_uow(self):
        return InMemoryUnitOfWork()

    async def test_aggregates_counts_from_all_modules(self, user_uow):
        for i in range(3):
            user = User.create(
                first_name=f"User{i}",
                last_name="Test",
                email_str=f"user{i}@test.com",
                plain_password="SecureP@ssw0rd123",
            )
            async with user_uow:
                await user_uow.users.save(user)

        competitions_repo = AsyncMock()
        competitions_repo.count_all = AsyncMock(return_value=12)
        competition_uow = _make_uow_mock(competitions=competitions_repo)

        quick_matches_repo = AsyncMock()
        quick_matches_repo.count_all = AsyncMock(return_value=58)
        quick_match_uow = _make_uow_mock(quick_matches=quick_matches_repo)

        golf_courses_repo = AsyncMock()
        golf_courses_repo.count_by_approval_status = AsyncMock(
            side_effect=lambda status: 9 if status is ApprovalStatus.APPROVED else 2
        )
        golf_course_uow = _make_uow_mock(golf_courses=golf_courses_repo)

        use_case = GetAdminStatsUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)
        stats = await use_case.execute()

        assert stats.total_users == 3
        assert stats.total_competitions == 12
        assert stats.total_quick_matches == 58
        assert stats.total_golf_courses_approved == 9
        assert stats.total_golf_courses_pending == 2
