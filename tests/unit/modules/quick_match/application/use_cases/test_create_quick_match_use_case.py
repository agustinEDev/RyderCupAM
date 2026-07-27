"""Tests para CreateQuickMatchUseCase."""

from uuid import uuid4

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.quick_match.application.dto.quick_match_dto import CreateQuickMatchRequestDTO
from src.modules.quick_match.application.exceptions import (
    GolfCourseNotApprovedError,
    GolfCourseNotFoundError,
)
from src.modules.quick_match.application.use_cases.create_quick_match_use_case import (
    CreateQuickMatchUseCase,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.quick_match.conftest import create_golf_course, create_user

pytestmark = pytest.mark.asyncio


class TestCreateQuickMatchUseCase:
    async def test_create_success(self, qm_uow, golf_course_uow, user_uow):
        creator = await create_user(user_uow, "creator@test.com")
        golf_course = await create_golf_course(golf_course_uow, creator.id)

        use_case = CreateQuickMatchUseCase(qm_uow, golf_course_uow, user_uow)
        response = await use_case.execute(
            CreateQuickMatchRequestDTO(
                creator_id=creator.id.value,
                golf_course_id=golf_course.id.value,
                match_format="SINGLES",
            )
        )

        assert response.status == "PENDING"
        assert response.creator_id == creator.id.value
        assert len(response.participants) == 1
        assert response.participants[0].user_id == creator.id.value

    async def test_create_free_play_success(self, qm_uow, golf_course_uow, user_uow):
        creator = await create_user(user_uow, "creator-freeplay@test.com")
        golf_course = await create_golf_course(golf_course_uow, creator.id)

        use_case = CreateQuickMatchUseCase(qm_uow, golf_course_uow, user_uow)
        response = await use_case.execute(
            CreateQuickMatchRequestDTO(
                creator_id=creator.id.value,
                golf_course_id=golf_course.id.value,
                scoring_format="STABLEFORD",
            )
        )

        assert response.match_format is None
        assert response.scoring_format == "STABLEFORD"
        assert response.participants[0].team is None

    async def test_golf_course_not_found_raises(self, qm_uow, golf_course_uow, user_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        use_case = CreateQuickMatchUseCase(qm_uow, golf_course_uow, user_uow)

        with pytest.raises(GolfCourseNotFoundError):
            await use_case.execute(
                CreateQuickMatchRequestDTO(
                    creator_id=creator.id.value,
                    golf_course_id=uuid4(),
                    match_format="SINGLES",
                )
            )

    async def test_unapproved_golf_course_raises(self, qm_uow, golf_course_uow, user_uow):
        creator = await create_user(user_uow, "creator3@test.com")
        holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]
        tees = [
            Tee(
                category=TeeCategory.CHAMPIONSHIP,
                gender=Gender.MALE,
                identifier="White",
                course_rating=72.0,
                slope_rating=130,
            ),
            Tee(
                category=TeeCategory.AMATEUR,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            ),
        ]
        pending_course = GolfCourse.create(
            name="Pending Golf Club",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator.id,
            tees=tees,
            holes=holes,
        )
        async with golf_course_uow:
            await golf_course_uow.golf_courses.save(pending_course)

        use_case = CreateQuickMatchUseCase(qm_uow, golf_course_uow, user_uow)
        with pytest.raises(GolfCourseNotApprovedError):
            await use_case.execute(
                CreateQuickMatchRequestDTO(
                    creator_id=creator.id.value,
                    golf_course_id=pending_course.id.value,
                    match_format="SINGLES",
                )
            )
