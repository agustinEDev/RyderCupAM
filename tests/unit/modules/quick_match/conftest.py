"""Fixtures y helpers compartidos para los tests unitarios del modulo QuickMatch."""

from uuid import uuid4

import pytest

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


@pytest.fixture
def qm_uow():
    return InMemoryQuickMatchUnitOfWork()


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def golf_course_uow():
    return InMemoryGolfCourseUnitOfWork()


@pytest.fixture
def user_uow():
    return UserInMemoryUoW()


async def create_user(user_uow, email: str):
    user = User.create(
        first_name="Test",
        last_name="User",
        email_str=email,
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def create_golf_course(golf_course_uow, creator_id):
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
    holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

    golf_course = GolfCourse.create(
        name="Test Golf Club",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=tees,
        holes=holes,
    )
    golf_course.approve()
    async with golf_course_uow:
        await golf_course_uow.golf_courses.save(golf_course)
    return golf_course


async def create_accepted_friendship(social_uow, user_id_a, user_id_b):
    friendship = Friendship.create(
        id=FriendshipId.generate(), requester_id=user_id_a, addressee_id=user_id_b
    )
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)
    return friendship


def unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}@test.com"
