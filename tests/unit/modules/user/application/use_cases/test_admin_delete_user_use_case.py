"""Tests para AdminDeleteUserUseCase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.user.application.use_cases.admin_delete_user_use_case import (
    AdminDeleteUserUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.exceptions import UserHasActivityException
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


def _make_uow_mock(**repo_attrs):
    """Crea un UoW mock cuyo __aenter__/__aexit__ funcionan como context manager."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    for name, repo in repo_attrs.items():
        setattr(uow, name, repo)
    return uow


class TestAdminDeleteUserUseCase:
    @pytest.fixture
    def user_uow(self):
        return InMemoryUnitOfWork()

    @pytest.fixture
    async def existing_user(self, user_uow):
        user = User.create(
            first_name="Carlos",
            last_name="Ruiz",
            email_str="carlos@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with user_uow:
            await user_uow.users.save(user)
        return user

    def _make_use_case(
        self,
        user_uow,
        competitions_created=0,
        has_scores=False,
        quick_match_created=False,
        golf_courses_created=0,
    ):
        competitions_repo = AsyncMock()
        competitions_repo.count_by_creator = AsyncMock(return_value=competitions_created)
        hole_scores_repo = AsyncMock()
        hole_scores_repo.exists_by_player = AsyncMock(return_value=has_scores)
        competition_uow = _make_uow_mock(
            competitions=competitions_repo, hole_scores=hole_scores_repo
        )

        quick_matches_repo = AsyncMock()
        quick_matches_repo.exists_created_by = AsyncMock(return_value=quick_match_created)
        quick_match_uow = _make_uow_mock(quick_matches=quick_matches_repo)

        golf_courses_repo = AsyncMock()
        golf_courses_repo.count_by_creator = AsyncMock(return_value=golf_courses_created)
        golf_course_uow = _make_uow_mock(golf_courses=golf_courses_repo)

        return AdminDeleteUserUseCase(user_uow, competition_uow, quick_match_uow, golf_course_uow)

    async def test_deletes_user_with_no_activity(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow)
        await use_case.execute(str(existing_user.id.value))

        async with user_uow:
            assert await user_uow.users.find_by_id(existing_user.id) is None

    async def test_blocks_delete_when_user_created_competitions(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow, competitions_created=2)

        with pytest.raises(UserHasActivityException) as exc_info:
            await use_case.execute(str(existing_user.id.value))
        assert "2 competition(s)" in str(exc_info.value)

        async with user_uow:
            assert await user_uow.users.find_by_id(existing_user.id) is not None

    async def test_blocks_delete_when_user_has_hole_scores(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow, has_scores=True)

        with pytest.raises(UserHasActivityException):
            await use_case.execute(str(existing_user.id.value))

    async def test_blocks_delete_when_user_created_quick_match(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow, quick_match_created=True)

        with pytest.raises(UserHasActivityException):
            await use_case.execute(str(existing_user.id.value))

    async def test_blocks_delete_when_user_requested_golf_course(self, user_uow, existing_user):
        use_case = self._make_use_case(user_uow, golf_courses_created=1)

        with pytest.raises(UserHasActivityException):
            await use_case.execute(str(existing_user.id.value))

    async def test_raises_not_found_before_checking_activity(self, user_uow):
        from uuid import uuid4

        use_case = self._make_use_case(user_uow)
        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(uuid4()))
