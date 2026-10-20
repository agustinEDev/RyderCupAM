"""In-Memory Hole Report Repository (testing)."""

from uuid import UUID

from src.modules.golf_course.domain.entities.hole_report import HoleReport
from src.modules.golf_course.domain.repositories.hole_report_repository import (
    IHoleReportRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId


class InMemoryHoleReportRepository(IHoleReportRepository):
    """Reportes de hoyo con su número de llegada, como `seq` en PostgreSQL."""

    def __init__(self) -> None:
        self._reports: dict[UUID, tuple[int, HoleReport]] = {}
        self._next_seq = 1

    async def lock_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> None:
        """En memoria no hay dos transacciones a la vez: nada que bloquear."""

    async def exists(self, report_id: UUID) -> bool:
        return report_id in self._reports

    async def count_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        return sum(
            1
            for _, report in self._reports.values()
            if report.golf_course_id == golf_course_id and report.hole_number == hole_number
        )

    async def add(self, report: HoleReport) -> bool:
        if report.id in self._reports:
            return False  # Como ON CONFLICT (id) DO NOTHING
        self._reports[report.id] = (self._next_seq, report)
        self._next_seq += 1
        return True

    async def delete(self, golf_course_id: GolfCourseId, report_id: UUID) -> bool:
        found = self._reports.get(report_id)
        if found is None or found[1].golf_course_id != golf_course_id:
            return False
        del self._reports[report_id]
        return True

    async def delete_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        ids = [
            report_id
            for report_id, (_, report) in self._reports.items()
            if report.golf_course_id == golf_course_id and report.hole_number == hole_number
        ]
        for report_id in ids:
            del self._reports[report_id]
        return len(ids)

    async def count_by_hole(self) -> list[tuple[GolfCourseId, int, int]]:
        counts: dict[tuple[GolfCourseId, int], int] = {}
        for _, report in self._reports.values():
            key = (report.golf_course_id, report.hole_number)
            counts[key] = counts.get(key, 0) + 1
        return [(course, hole, n) for (course, hole), n in counts.items()]

    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleReport]:
        mine = [
            (report.hole_number, seq, report)
            for seq, report in self._reports.values()
            if report.golf_course_id == golf_course_id
        ]
        return [report for _, _, report in sorted(mine, key=lambda row: row[:2])]
