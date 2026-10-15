"""
Caso de uso: importar de OpenStreetMap el mapa de hoyos de un campo (BE #532).

Solo campos aprobados con coordenadas. Lo importado queda pendiente de que un
admin lo revise, y un mapa que ya aprobó nunca se pisa: ni se pregunta a OSM.
En seco (sin `apply`) calcula y dice qué haría, sin guardar nada.
"""

from datetime import UTC, datetime

from src.modules.golf_course.application.dtos.hole_map_import_dtos import (
    ImportHoleMapRequestDTO,
    ImportHoleMapResponseDTO,
    ImportHoleMapStatus,
)
from src.modules.golf_course.application.ports.osm_hole_map_source import (
    CardHole,
    IOsmHoleMapSource,
    OsmUnavailableError,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus

# Un campo sin hoyos sobre el terreno declarados es uno de 18
DEFAULT_PHYSICAL_HOLES = 18


class ImportHoleMapFromOsmUseCase:
    """Importa (o reimporta) el mapa de hoyos de un campo desde OSM."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface, source: IOsmHoleMapSource) -> None:
        self._uow = uow
        self._source = source

    async def execute(self, request: ImportHoleMapRequestDTO) -> ImportHoleMapResponseDTO:
        """
        Importa el mapa del campo.

        Raises:
            ValueError: si el campo no existe o no está aprobado
        """
        async with self._uow:
            course_id = GolfCourseId(request.golf_course_id)
            course = await self._uow.golf_courses.find_by_id(course_id)
            if course is None:
                raise ValueError(f"Golf course not found: {request.golf_course_id}")
            if not course.approval_status.is_approved():
                raise ValueError(
                    f"Only approved golf courses get a hole map: {request.golf_course_id}"
                )

            location = course.location
            if location.latitude is None or location.longitude is None:
                return ImportHoleMapResponseDTO(status=ImportHoleMapStatus.NO_COORDINATES)

            existing = await self._uow.hole_maps.find_by_golf_course_id(course_id)
            if existing is not None and existing.status is HoleMapStatus.APPROVED:
                return ImportHoleMapResponseDTO(status=ImportHoleMapStatus.SKIPPED_APPROVED)

            try:
                candidate = await self._source.find(
                    latitude=location.latitude,
                    longitude=location.longitude,
                    card=[
                        CardHole(number=h.number, par=h.par, stroke_index=h.stroke_index)
                        for h in course.reference_card
                    ],
                    physical_holes=course.physical_holes or DEFAULT_PHYSICAL_HOLES,
                )
            except OsmUnavailableError:
                return ImportHoleMapResponseDTO(status=ImportHoleMapStatus.OSM_UNAVAILABLE)

            if candidate is None:
                return ImportHoleMapResponseDTO(status=ImportHoleMapStatus.NO_OUTLINE)

            discarded = {reason.value: count for reason, count in candidate.discarded.items()}
            if not candidate.holes:
                return ImportHoleMapResponseDTO(
                    status=ImportHoleMapStatus.NO_VALID_HOLES,
                    discarded=discarded,
                    osm_reference=candidate.osm_reference,
                )

            status = (
                ImportHoleMapStatus.CREATED if existing is None else ImportHoleMapStatus.REIMPORTED
            )
            if request.apply:
                now = datetime.now(UTC).replace(tzinfo=None)
                if existing is None:
                    hole_map = CourseHoleMap.create(
                        golf_course_id=course_id,
                        holes=candidate.holes,
                        osm_reference=candidate.osm_reference,
                        imported_at=now,
                    )
                else:
                    existing.reimport(
                        holes=candidate.holes,
                        osm_reference=candidate.osm_reference,
                        imported_at=now,
                    )
                    hole_map = existing
                await self._uow.hole_maps.save(hole_map)

            return ImportHoleMapResponseDTO(
                status=status,
                holes_imported=len(candidate.holes),
                discarded=discarded,
                osm_reference=candidate.osm_reference,
            )
