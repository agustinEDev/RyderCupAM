"""Hole Sample Repository - SQLAlchemy Implementation (BE #532, 16 oct 2026)."""

from typing import Any

from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.repositories.hole_sample_repository import (
    IHoleSampleRepository,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.infrastructure.persistence.mappers.hole_sample_mapper import (
    golf_course_hole_samples_table,
)

_table = golf_course_hole_samples_table

# Bloqueo consultivo de la transacción, con clave por campo y hoyo. El prefijo
# lo separa de otros bloqueos consultivos de la app
_LOCK_HOLE = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")


def _from_row(row: Any) -> HoleSample:
    return HoleSample.reconstruct(
        id=row.id,
        golf_course_id=row.golf_course_id,
        hole_number=row.hole_number,
        tee=GeoPoint(latitude=row.tee_latitude, longitude=row.tee_longitude),
        bends=[GeoPoint(latitude=lat, longitude=lon) for lat, lon in row.bends],
        green_center=GeoPoint(latitude=row.green_latitude, longitude=row.green_longitude),
        created_at=row.created_at,
    )


class HoleSampleRepository(IHoleSampleRepository):
    """Repositorio de muestras de hoyo con SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> None:
        # Se suelta solo al confirmar o deshacer la transacción
        await self._session.execute(
            _LOCK_HOLE, {"key": f"golf_course_hole_samples:{golf_course_id}:{hole_number}"}
        )

    async def count_for_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(_table)
            .where(_table.c.golf_course_id == golf_course_id, _table.c.hole_number == hole_number)
        )
        return int(result.scalar_one())

    async def add(self, sample: HoleSample) -> None:
        await self._session.execute(
            insert(_table).values(
                id=sample.id,
                golf_course_id=sample.golf_course_id,
                hole_number=sample.hole_number,
                tee_latitude=sample.tee.latitude,
                tee_longitude=sample.tee.longitude,
                bends=[[bend.latitude, bend.longitude] for bend in sample.bends],
                green_latitude=sample.green_center.latitude,
                green_longitude=sample.green_center.longitude,
                created_at=sample.created_at,
            )
        )

    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleSample]:
        # El id solo desempata dos que llegasen en el mismo microsegundo
        result = await self._session.execute(
            select(_table)
            .where(_table.c.golf_course_id == golf_course_id)
            .order_by(_table.c.hole_number, _table.c.created_at, _table.c.id)
        )
        return [_from_row(row) for row in result]
