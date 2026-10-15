"""In-Memory Hole Mark Repository (testing)."""

from src.modules.golf_course.domain.entities.hole_mark import HoleMark
from src.modules.golf_course.domain.repositories.hole_mark_repository import (
    IHoleMarkRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryHoleMarkRepository(IHoleMarkRepository):
    """Marcas de hoyo en un diccionario, por (campo, hoyo, jugador)."""

    def __init__(self) -> None:
        self._marks: dict[tuple[str, int, str], HoleMark] = {}

    async def save(self, mark: HoleMark) -> None:
        key = (str(mark.golf_course_id), mark.hole_number, str(mark.user_id))
        previous = self._marks.get(key)
        if previous is not None:
            # Como el upsert de PostgreSQL: la fecha de la primera marca se queda
            mark = HoleMark(
                golf_course_id=mark.golf_course_id,
                hole_number=mark.hole_number,
                user_id=mark.user_id,
                tee=mark.tee,
                bends=mark.bends,
                green_center=mark.green_center,
                created_at=previous.created_at,
                updated_at=mark.updated_at,
            )
        self._marks[key] = mark

    async def find_by_course_and_user(
        self, golf_course_id: GolfCourseId, user_id: UserId
    ) -> list[HoleMark]:
        mine = [
            mark
            for (course, _, user), mark in self._marks.items()
            if course == str(golf_course_id) and user == str(user_id)
        ]
        return sorted(mine, key=lambda mark: mark.hole_number)
