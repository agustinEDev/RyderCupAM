"""Saved Hole Repository - SQLAlchemy Implementation (BE #575, 17 oct 2026)."""

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.golf_course.domain.entities.saved_hole import SavedHole
from src.modules.golf_course.domain.repositories.saved_hole_repository import (
    ISavedHoleRepository,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.infrastructure.persistence.mappers.saved_hole_mapper import (
    golf_course_saved_holes_table,
)

_table = golf_course_saved_holes_table


def _from_row(row: Any) -> SavedHole:
    return SavedHole.reconstruct(
        golf_course_id=row.golf_course_id,
        hole_number=row.hole_number,
        tee=GeoPoint(latitude=row.tee_latitude, longitude=row.tee_longitude),
        bends=[GeoPoint(latitude=lat, longitude=lon) for lat, lon in row.bends],
        green_center=GeoPoint(latitude=row.green_latitude, longitude=row.green_longitude),
        saved_by=row.saved_by,
        saved_at=row.saved_at,
    )


class SavedHoleRepository(ISavedHoleRepository):
    """Repositorio de las líneas guardadas de los hoyos con SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, hole: SavedHole) -> None:
        values = {
            "tee_latitude": hole.tee.latitude,
            "tee_longitude": hole.tee.longitude,
            "bends": [[bend.latitude, bend.longitude] for bend in hole.bends],
            "green_latitude": hole.green_center.latitude,
            "green_longitude": hole.green_center.longitude,
            "saved_by": hole.saved_by,
            "saved_at": hole.saved_at,
        }
        # Guardar encima: la línea nueva sustituye a la de antes, sin carrera
        statement = (
            insert(_table)
            .values(golf_course_id=hole.golf_course_id, hole_number=hole.hole_number, **values)
            .on_conflict_do_update(
                index_elements=[_table.c.golf_course_id, _table.c.hole_number], set_=values
            )
        )
        await self._session.execute(statement)

    async def get(self, golf_course_id: GolfCourseId, hole_number: int) -> SavedHole | None:
        result = await self._session.execute(
            select(_table).where(
                _table.c.golf_course_id == golf_course_id, _table.c.hole_number == hole_number
            )
        )
        row = result.first()
        return _from_row(row) if row else None

    async def list_by_course(self, golf_course_id: GolfCourseId) -> list[SavedHole]:
        result = await self._session.execute(
            select(_table)
            .where(_table.c.golf_course_id == golf_course_id)
            .order_by(_table.c.hole_number)
        )
        return [_from_row(row) for row in result]

    async def list_all(self) -> list[SavedHole]:
        result = await self._session.execute(select(_table))
        return [_from_row(row) for row in result]

    async def delete(self, golf_course_id: GolfCourseId, hole_number: int) -> bool:
        result = await self._session.execute(
            delete(_table)
            .where(_table.c.golf_course_id == golf_course_id, _table.c.hole_number == hole_number)
            .returning(_table.c.hole_number)
        )
        return result.first() is not None
