"""In-Memory Hole Sample Repository (testing)."""

from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.repositories.hole_sample_repository import (
    IHoleSampleRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class InMemoryHoleSampleRepository(IHoleSampleRepository):
    """Muestras de hoyo en una lista, en orden de llegada."""

    def __init__(self) -> None:
        self._samples: list[HoleSample] = []

    async def lock_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> None:
        """En memoria no hay dos transacciones a la vez: nada que bloquear."""

    async def count_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        return sum(
            1
            for sample in self._samples
            if sample.golf_course_id == golf_course_id and sample.hole_number == hole_number
        )

    async def add(self, sample: HoleSample) -> None:
        self._samples.append(sample)

    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleSample]:
        mine = [s for s in self._samples if s.golf_course_id == golf_course_id]
        # sorted es estable: a igual fecha, el orden de llegada
        return sorted(mine, key=lambda s: (s.hole_number, s.created_at))
