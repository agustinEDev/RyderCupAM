"""In-Memory Saved Hole Repository (testing)."""

from src.modules.golf_course.domain.entities.saved_hole import SavedHole
from src.modules.golf_course.domain.repositories.saved_hole_repository import (
    ISavedHoleRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class InMemorySavedHoleRepository(ISavedHoleRepository):
    """Una línea por campo y hoyo, como la clave primaria de la tabla."""

    def __init__(self) -> None:
        self._holes: dict[tuple[GolfCourseId, int], SavedHole] = {}

    async def save(self, hole: SavedHole) -> None:
        self._holes[(hole.golf_course_id, hole.hole_number)] = hole

    async def get(self, golf_course_id: GolfCourseId, hole_number: int) -> SavedHole | None:
        return self._holes.get((golf_course_id, hole_number))

    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[SavedHole]:
        return sorted(
            (h for (course, _), h in self._holes.items() if course == golf_course_id),
            key=lambda h: h.hole_number,
        )

    async def list_all(self) -> list[SavedHole]:
        return list(self._holes.values())

    async def delete(self, golf_course_id: GolfCourseId, hole_number: int) -> bool:
        return self._holes.pop((golf_course_id, hole_number), None) is not None
