"""
Caso de uso: importar de OpenStreetMap el mapa de hoyos de un campo (BE #532).

Solo campos aprobados con coordenadas. Lo importado entra aprobado y reimportar
sustituye el mapa, esté como esté (Agustín, 17-18 oct): lo que corrige el admin
va en la línea guardada de cada hoyo, aparte, y prevalece sobre OSM. En seco
(sin `apply`) calcula y dice qué haría, sin guardar nada.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from src.modules.golf_course.application.dtos.hole_map_import_dtos import (
    ImportHoleMapRequestDTO,
    ImportHoleMapResponseDTO,
    ImportHoleMapStatus,
)
from src.modules.golf_course.application.ports.osm_hole_map_source import (
    CardHole,
    IOsmHoleMapSource,
    OsmHoleMapCandidate,
    OsmUnavailableError,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

# Un campo sin hoyos sobre el terreno declarados es uno de 18
DEFAULT_PHYSICAL_HOLES = 18


@dataclass(frozen=True)
class _Plan:
    """Lo leído del campo antes de preguntar a OSM."""

    course_id: GolfCourseId
    latitude: float
    longitude: float
    card: list[CardHole]
    physical_holes: int
    has_map: bool


class ImportHoleMapFromOsmUseCase:
    """Importa (o reimporta) el mapa de hoyos de un campo desde OSM."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface, source: IOsmHoleMapSource) -> None:
        self._uow = uow
        self._source = source

    async def execute(self, request: ImportHoleMapRequestDTO) -> ImportHoleMapResponseDTO:
        """
        Importa el mapa del campo.

        Tres pasos, para no tener una transacción abierta mientras se espera a
        OSM (puede tardar minutos): leer el campo, preguntar a OSM y, al
        guardar, volver a leer el mapa, por si mientras tanto otra pasada lo creó
        (o un admin lo revisó): se reimporta, no se crea otro.

        Raises:
            ValueError: si el campo no existe o no está aprobado
        """
        plan = await self._read(GolfCourseId(request.golf_course_id))
        if isinstance(plan, ImportHoleMapResponseDTO):
            return plan
        candidate = await self._ask(plan)
        if isinstance(candidate, ImportHoleMapResponseDTO):
            return candidate
        if not request.apply:
            status = ImportHoleMapStatus.REIMPORTED if plan.has_map else ImportHoleMapStatus.CREATED
            return _result(status, candidate)
        return await self._save(plan.course_id, candidate)

    async def _read(self, course_id: GolfCourseId) -> _Plan | ImportHoleMapResponseDTO:
        async with self._uow:
            course = await self._uow.golf_courses.find_by_id(course_id)
            if course is None:
                raise ValueError(f"Golf course not found: {course_id}")
            if not course.approval_status.is_approved():
                raise ValueError(f"Only approved golf courses get a hole map: {course_id}")
            latitude, longitude = course.location.latitude, course.location.longitude
            if latitude is None or longitude is None:
                return ImportHoleMapResponseDTO(status=ImportHoleMapStatus.NO_COORDINATES)
            existing = await self._uow.hole_maps.find_by_golf_course_id(course_id)
            return _Plan(
                course_id=course_id,
                latitude=latitude,
                longitude=longitude,
                card=[
                    CardHole(number=h.number, par=h.par, stroke_index=h.stroke_index)
                    for h in course.reference_card
                ],
                physical_holes=course.physical_holes or DEFAULT_PHYSICAL_HOLES,
                has_map=existing is not None,
            )

    async def _ask(self, plan: _Plan) -> OsmHoleMapCandidate | ImportHoleMapResponseDTO:
        """Pregunta a OSM, sin ninguna transacción abierta."""
        try:
            candidate = await self._source.find(
                latitude=plan.latitude,
                longitude=plan.longitude,
                card=plan.card,
                physical_holes=plan.physical_holes,
            )
        except OsmUnavailableError:
            return ImportHoleMapResponseDTO(status=ImportHoleMapStatus.OSM_UNAVAILABLE)
        if candidate is None:
            return ImportHoleMapResponseDTO(status=ImportHoleMapStatus.NO_OUTLINE)
        if not candidate.holes:
            return _result(ImportHoleMapStatus.NO_VALID_HOLES, candidate)
        # Con menos de la mitad no hay mapa: el campo va como sin mapear (GPS y marcar)
        if len(candidate.holes) * 2 < plan.physical_holes:
            return _result(ImportHoleMapStatus.TOO_FEW_HOLES, candidate)
        return candidate

    async def _save(
        self, course_id: GolfCourseId, candidate: OsmHoleMapCandidate
    ) -> ImportHoleMapResponseDTO:
        """Vuelve a leer el mapa y lo crea o lo reimporta."""
        async with self._uow:
            # Lo último de la BD y bloqueado: otra pasada pudo crearlo mientras OSM respondía
            current = await self._uow.hole_maps.find_by_golf_course_id_for_update(course_id)
            now = datetime.now(UTC).replace(tzinfo=None)
            if current is None:
                current = CourseHoleMap.create_approved(
                    golf_course_id=course_id,
                    holes=candidate.holes,
                    osm_reference=candidate.osm_reference,
                    imported_at=now,
                )
                status = ImportHoleMapStatus.CREATED
            else:
                current.reimport(
                    holes=candidate.holes, osm_reference=candidate.osm_reference, imported_at=now
                )
                status = ImportHoleMapStatus.REIMPORTED
            await self._uow.hole_maps.save(current)
        return _result(status, candidate)


def _result(
    status: ImportHoleMapStatus, candidate: OsmHoleMapCandidate
) -> ImportHoleMapResponseDTO:
    """El resultado con el recuento del candidato de OSM."""
    return ImportHoleMapResponseDTO(
        status=status,
        holes_imported=len(candidate.holes),
        discarded={reason.value: count for reason, count in candidate.discarded.items()},
        osm_reference=candidate.osm_reference,
    )
