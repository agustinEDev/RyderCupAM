"""
Casos de uso de los reportes de hoyo (entrega 7, aprobada por Agustín el 18 oct 2026).

- Mandar: un jugador reporta un hoyo con línea (guardada por el admin, del mapa
  de OSM aprobado o de una muestra completa) con un motivo y la línea que
  propone. Se guarda si es válido, si su id es nuevo, si el hoyo tiene menos de
  tres reportes abiertos y si el jugador no reportó ya ese hoyo en los últimos
  10 minutos. Si no, se responde igual y no se guarda nada: el jugador no lo
  nota. Como una muestra, no se guarda quién lo mandó.
- Descartar: el admin borra un reporte (que quien llama es admin lo mira la
  ruta). Guardar la línea del hoyo cierra todos los suyos (SaveHoleLineUseCase).

Los reportes no cambian lo que ven los jugadores: el hoyo vuelve a
«Pendientes» del admin y, mientras, todos siguen viendo la línea de siempre.
"""

import logging

from src.modules.golf_course.application.dtos.hole_report_dtos import (
    DiscardHoleReportRequestDTO,
    SubmitHoleReportRequestDTO,
    SubmitHoleReportResponseDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleNotInCourseError,
    HoleReportNotFoundError,
)
from src.modules.golf_course.application.ports.recent_hole_sample_senders import (
    IRecentHoleSampleSenders,
)
from src.modules.golf_course.application.use_cases.hole_points import (
    location_of,
    to_point,
    visible,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole_report import (
    MAX_REPORTS_PER_HOLE,
    HoleReport,
    InvalidHoleReportError,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.mapped_hole import (
    MAX_HOLE_NUMBER,
    MIN_HOLE_NUMBER,
)

logger = logging.getLogger(__name__)


class SubmitHoleReportUseCase:
    """
    Llega el reporte de un hoyo: se guarda si es válido, si el hoyo tiene línea y
    menos de tres reportes, si su id es nuevo y si el jugador no reportó ya ese
    hoyo en los últimos 10 minutos.
    """

    def __init__(
        self, uow: GolfCourseUnitOfWorkInterface, recent_senders: IRecentHoleSampleSenders
    ) -> None:
        self._uow = uow
        self._recent_senders = recent_senders

    async def execute(self, request: SubmitHoleReportRequestDTO) -> SubmitHoleReportResponseDTO:
        """
        La respuesta es la misma se guarde o no: quien lo manda nunca nota la diferencia.

        Raises:
            GolfCourseNotFoundError: si el campo no existe o no lo ven los jugadores
            HoleNotInCourseError: si el hoyo no es del 1 al 18
        """
        course_id = GolfCourseId(request.golf_course_id)
        hole = request.hole_number
        reserved: tuple | None = None
        accepted = False
        try:
            async with self._uow:
                course = await self._uow.golf_courses.find_by_id(course_id)
                if not visible(course):
                    raise GolfCourseNotFoundError(request.golf_course_id)
                if not MIN_HOLE_NUMBER <= hole <= MAX_HOLE_NUMBER:
                    raise HoleNotInCourseError(hole)
                report = self._report(request, course, course_id)
                if report is None:
                    return SubmitHoleReportResponseDTO()
                key = (request.user_id, course_id, hole)
                if not self._recent_senders.reserve(*key):
                    logger.debug(
                        "Hole report not stored (course %s, hole %s): sender window",
                        course_id,
                        hole,
                    )
                    return SubmitHoleReportResponseDTO()
                reserved = key
                stored = await self._store(report)
            # Aquí la transacción ya se confirmó: si el commit falla, no se llega
            accepted = stored
        finally:
            # Solo gasta la ventana un reporte guardado y confirmado
            if reserved is not None:
                if accepted:
                    self._recent_senders.confirm(*reserved)
                else:
                    self._recent_senders.release(*reserved)
        return SubmitHoleReportResponseDTO()

    def _report(
        self, request: SubmitHoleReportRequestDTO, course: GolfCourse, course_id: GolfCourseId
    ) -> HoleReport | None:
        """El reporte, o None si el dominio lo rechaza. En los logs, nunca coordenadas ni quién."""
        try:
            return HoleReport.create(
                id=request.id,
                golf_course_id=course_id,
                hole_number=request.hole_number,
                reason=request.reason,
                tee=to_point(request.tee, InvalidHoleReportError),
                bends=[to_point(bend, InvalidHoleReportError) for bend in request.bends],
                green_center=to_point(request.green_center, InvalidHoleReportError),
                course_location=location_of(course),
            )
        except InvalidHoleReportError as e:
            logger.info(
                "Hole report dropped (course %s, hole %s): %s",
                course_id,
                request.hole_number,
                type(e).__name__,
            )
            return None

    async def _has_line(self, course_id: GolfCourseId, hole: int) -> bool:
        """
        Si el hoyo tiene una línea que reportar: la guardada por el admin, la del
        mapa de OSM aprobado o la de una muestra completa (R1).
        """
        if await self._uow.saved_holes.get(course_id, hole) is not None:
            return True
        hole_map = await self._uow.hole_maps.find_by_golf_course_id(course_id)
        if hole_map is not None and hole_map.is_approved and hole_map.hole(hole) is not None:
            return True
        samples = self._uow.hole_samples
        complete = await samples.count_for_hole(course_id, hole) - int(
            await samples.has_green_only(course_id, hole)
        )
        return complete > 0

    async def _store(self, report: HoleReport) -> bool:
        """
        Guarda el reporte si su hoyo tiene línea, su id es nuevo y caben más. Con
        el hoyo bloqueado: dos que lleguen a la vez no pueden dejar cuatro.
        """
        course_id, hole = report.golf_course_id, report.hole_number
        reports = self._uow.hole_reports
        await reports.lock_hole(course_id, hole)
        # Lo barato primero (un reenvío, un hoyo lleno); si el hoyo tiene línea,
        # después: carga el mapa del campo (/code-review, 18 oct)
        if await reports.exists(report.id):
            logger.debug(
                "Hole report not stored (course %s, hole %s): repeated id", course_id, hole
            )
            return False
        if await reports.count_for_hole(course_id, hole) >= MAX_REPORTS_PER_HOLE:
            logger.debug(
                "Hole report not stored (course %s, hole %s): hole already has its reports",
                course_id,
                hole,
            )
            return False
        if not await self._has_line(course_id, hole):
            logger.debug("Hole report not stored (course %s, hole %s): no line", course_id, hole)
            return False
        return await reports.add(report)


class DiscardHoleReportUseCase:
    """El admin descarta un reporte de un campo."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: DiscardHoleReportRequestDTO) -> None:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe
            HoleReportNotFoundError: si el reporte no está en ese campo
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            if await self._uow.golf_courses.find_by_id(course_id) is None:
                raise GolfCourseNotFoundError(request.golf_course_id)
            if not await self._uow.hole_reports.delete(course_id, request.report_id):
                raise HoleReportNotFoundError(str(request.report_id))
