"""Hole Report Repository - SQLAlchemy Implementation (entrega 7, 18 oct 2026)."""

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.golf_course.domain.entities.hole_report import HoleReport, HoleReportReason
from src.modules.golf_course.domain.repositories.hole_report_repository import (
    IHoleReportRepository,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.infrastructure.persistence.mappers.hole_report_mapper import (
    golf_course_hole_reports_table,
)

_table = golf_course_hole_reports_table

# El mismo bloqueo consultivo que las muestras, con otra clave: un reporte y una
# muestra del mismo hoyo no se esperan entre sí
_LOCK_HOLE = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")


def _from_row(row: Any) -> HoleReport:
    return HoleReport.reconstruct(
        id=row.id,
        golf_course_id=row.golf_course_id,
        hole_number=row.hole_number,
        reason=HoleReportReason(row.reason),
        tee=GeoPoint(latitude=row.tee_latitude, longitude=row.tee_longitude),
        bends=[GeoPoint(latitude=lat, longitude=lon) for lat, lon in row.bends],
        green_center=GeoPoint(latitude=row.green_latitude, longitude=row.green_longitude),
        received_on=row.received_on,
    )


class HoleReportRepository(IHoleReportRepository):
    """Repositorio de reportes de hoyo con SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> None:
        # Se suelta solo al confirmar o deshacer la transacción
        key = f"golf_course_hole_reports:{golf_course_id}:{hole_number}"
        await self._session.execute(_LOCK_HOLE, {"key": key})

    async def exists(self, report_id: UUID) -> bool:
        result = await self._session.execute(select(_table.c.id).where(_table.c.id == report_id))
        return result.first() is not None

    async def count_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(_table)
            .where(
                _table.c.golf_course_id == golf_course_id,
                _table.c.hole_number == hole_number,
            )
        )
        return int(result.scalar_one())

    async def add(self, report: HoleReport) -> bool:
        # `seq` lo pone PostgreSQL (identidad): es el orden de llegada
        statement = (
            insert(_table)
            .values(
                id=report.id,
                golf_course_id=report.golf_course_id,
                hole_number=report.hole_number,
                reason=report.reason.value,
                tee_latitude=report.tee.latitude,
                tee_longitude=report.tee.longitude,
                bends=[[bend.latitude, bend.longitude] for bend in report.bends],
                green_latitude=report.green_center.latitude,
                green_longitude=report.green_center.longitude,
                received_on=report.received_on,
            )
            .on_conflict_do_nothing(index_elements=[_table.c.id])
            .returning(_table.c.id)
        )
        result = await self._session.execute(statement)
        return result.first() is not None

    async def delete(self, golf_course_id: GolfCourseId, report_id: UUID) -> bool:
        result = await self._session.execute(
            delete(_table)
            .where(_table.c.id == report_id, _table.c.golf_course_id == golf_course_id)
            .returning(_table.c.id)
        )
        return result.first() is not None

    async def delete_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        result = await self._session.execute(
            delete(_table)
            .where(
                _table.c.golf_course_id == golf_course_id,
                _table.c.hole_number == hole_number,
            )
            .returning(_table.c.id)
        )
        return len(result.all())

    async def count_by_hole(self) -> list[tuple[GolfCourseId, int, int]]:
        result = await self._session.execute(
            select(_table.c.golf_course_id, _table.c.hole_number, func.count()).group_by(
                _table.c.golf_course_id, _table.c.hole_number
            )
        )
        return [(row[0], row[1], int(row[2])) for row in result]

    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleReport]:
        result = await self._session.execute(
            select(_table)
            .where(_table.c.golf_course_id == golf_course_id)
            .order_by(_table.c.hole_number, _table.c.seq)
        )
        return [_from_row(row) for row in result]
