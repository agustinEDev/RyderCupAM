"""In-Memory Hole Sample Repository (testing)."""

from uuid import UUID

from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.repositories.hole_sample_repository import (
    IHoleSampleRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.gender import Gender


class InMemoryHoleSampleRepository(IHoleSampleRepository):
    """Muestras de hoyo con su número de llegada, como `seq` en PostgreSQL."""

    def __init__(self) -> None:
        self._samples: dict[UUID, tuple[int, HoleSample]] = {}
        self._next_seq = 1

    async def lock_tee(
        self,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> None:
        """En memoria no hay dos transacciones a la vez: nada que bloquear."""

    async def exists(self, sample_id: UUID) -> bool:
        return sample_id in self._samples

    async def count_for_tee(
        self,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
    ) -> int:
        return sum(
            1
            for _, sample in self._samples.values()
            if sample.golf_course_id == golf_course_id
            and sample.hole_number == hole_number
            and sample.tee_color == tee_color
            and sample.tee_gender == tee_gender
        )

    async def add(self, sample: HoleSample) -> bool:
        if sample.id in self._samples:
            return False  # Como ON CONFLICT (id) DO NOTHING
        self._samples[sample.id] = (self._next_seq, sample)
        self._next_seq += 1
        return True

    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleSample]:
        mine = [
            (sample.hole_number, seq, sample)
            for seq, sample in self._samples.values()
            if sample.golf_course_id == golf_course_id
        ]
        return [sample for _, _, sample in sorted(mine, key=lambda row: row[:2])]
