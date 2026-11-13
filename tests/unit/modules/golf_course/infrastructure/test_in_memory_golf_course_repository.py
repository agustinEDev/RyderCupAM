"""El doble en memoria del repositorio de campos responde igual que el de verdad."""

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_repository import (
    InMemoryGolfCourseRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


def _campo(creator_id: UserId, name: str) -> GolfCourse:
    return GolfCourse.create(
        name=name,
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=[
            Tee(
                color=TeeColor.WHITE,
                gender=Gender.MALE,
                identifier="White",
                course_rating=72.0,
                slope_rating=130,
            )
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
    )


async def test_find_by_creator_with_saved_courses_returns_only_that_creators():
    """
    Given: Two courses requested by one user and one by another
    When: Searching the courses of the first user
    Then: Only his two come back (the double read a `requested_by` that does not exist)
    """
    repo = InMemoryGolfCourseRepository()
    suyo, otro = UserId.generate(), UserId.generate()
    for campo in (_campo(suyo, "Uno"), _campo(suyo, "Dos"), _campo(otro, "Tres")):
        await repo.save(campo)

    encontrados = await repo.find_by_creator(suyo)

    assert sorted(c.name for c in encontrados) == ["Dos", "Uno"]


async def test_count_by_creator_with_saved_courses_counts_only_that_creators():
    """
    Given: One course requested by one user and one by another
    When: Counting the courses of the first user
    Then: It is one
    """
    repo = InMemoryGolfCourseRepository()
    suyo, otro = UserId.generate(), UserId.generate()
    await repo.save(_campo(suyo, "Uno"))
    await repo.save(_campo(otro, "Dos"))

    assert await repo.count_by_creator(suyo) == 1
