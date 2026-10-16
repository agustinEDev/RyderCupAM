"""Hole Sample Repository - SQLAlchemy Implementation (BE #532, 16 oct 2026)."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
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

# Bloqueo consultivo de la transacción, con una clave de 64 bits sacada del
# campo y el hoyo. Que choque con otra clave (la de otro hoyo, o el
# número fijo de otro bloqueo de la app, como el del vigilante de hándicaps) es
# muy improbable, y solo haría esperar a una de las dos: nunca da un resultado
# equivocado
_LOCK_HOLE = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")


def _from_row(row: Any) -> HoleSample:
    return HoleSample.reconstruct(
        id=row.id,
        golf_course_id=row.golf_course_id,
        hole_number=row.hole_number,
        tee_color=row.tee_color,
        tee_gender=row.tee_gender,
        # Sin salida: una muestra solo green (17 oct)
        tee=None
        if row.tee_latitude is None
        else GeoPoint(latitude=row.tee_latitude, longitude=row.tee_longitude),
        bends=[GeoPoint(latitude=lat, longitude=lon) for lat, lon in row.bends],
        green_center=GeoPoint(latitude=row.green_latitude, longitude=row.green_longitude),
        received_on=row.received_on,
    )


class HoleSampleRepository(IHoleSampleRepository):
    """Repositorio de muestras de hoyo con SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_hole(self, golf_course_id: GolfCourseId, hole_number: int) -> None:
        # Se suelta solo al confirmar o deshacer la transacción
        key = f"golf_course_hole_samples:{golf_course_id}:{hole_number}"
        await self._session.execute(_LOCK_HOLE, {"key": key})

    async def exists(self, sample_id: UUID) -> bool:
        result = await self._session.execute(select(_table.c.id).where(_table.c.id == sample_id))
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

    async def add(self, sample: HoleSample) -> bool:
        # `seq` lo pone PostgreSQL (identidad): es el orden de llegada
        statement = (
            insert(_table)
            .values(
                id=sample.id,
                golf_course_id=sample.golf_course_id,
                hole_number=sample.hole_number,
                tee_color=sample.tee_color,
                tee_gender=sample.tee_gender,
                tee_latitude=sample.tee.latitude if sample.tee else None,
                tee_longitude=sample.tee.longitude if sample.tee else None,
                bends=[[bend.latitude, bend.longitude] for bend in sample.bends],
                green_latitude=sample.green_center.latitude,
                green_longitude=sample.green_center.longitude,
                received_on=sample.received_on,
            )
            .on_conflict_do_nothing(index_elements=[_table.c.id])
            .returning(_table.c.id)
        )
        result = await self._session.execute(statement)
        return result.first() is not None

    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[HoleSample]:
        result = await self._session.execute(
            select(_table)
            .where(_table.c.golf_course_id == golf_course_id)
            .order_by(_table.c.hole_number, _table.c.seq)
        )
        return [_from_row(row) for row in result]
