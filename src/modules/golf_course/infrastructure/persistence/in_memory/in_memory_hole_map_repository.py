"""In-Memory Hole Map Repository (testing)."""

from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.repositories.hole_map_repository import IHoleMapRepository
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus


class InMemoryHoleMapRepository(IHoleMapRepository):
    """Mapas de hoyos en un diccionario, por campo."""

    def __init__(self) -> None:
        self._maps: dict[str, CourseHoleMap] = {}

    async def save(self, hole_map: CourseHoleMap) -> None:
        self._maps[str(hole_map.golf_course_id)] = hole_map

    async def find_by_golf_course_id(self, golf_course_id: GolfCourseId) -> CourseHoleMap | None:
        return self._maps.get(str(golf_course_id))

    async def find_pending(self) -> list[CourseHoleMap]:
        pending = [m for m in self._maps.values() if m.status is HoleMapStatus.PENDING_REVIEW]
        return sorted(pending, key=lambda m: m.imported_at)
