"""
Casos de uso de las muestras anónimas de hoyo (BE #532, reglas del 16 oct 2026).

- Mandar: por hoyo se guardan las tres primeras muestras que llegan. De la
  cuarta en adelante, o si el dominio la rechaza (codos de más, distancias
  imposibles, lejos del campo), se responde igual y no se guarda nada: el
  jugador no debe notarlo. Vale para cualquier hoyo, tenga o no datos en el mapa.
- Leer: de cada hoyo, la primera muestra y si sigue recogiendo. Nunca cuántas
  hay ni de quién son (no se guarda).
"""

import logging

from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    HoleSampleDTO,
    HoleSampleStatusDTO,
    ListHoleSamplesRequestDTO,
    PointDTO,
    SubmitHoleSampleRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleNotInCourseError,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole_sample import (
    MAX_SAMPLES_PER_HOLE,
    HoleSample,
    InvalidHoleSampleError,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.mapped_hole import (
    MAX_HOLE_NUMBER,
    MIN_HOLE_NUMBER,
)

logger = logging.getLogger(__name__)


def _visible(course: GolfCourse | None) -> bool:
    """
    Un campo que ven los jugadores: aprobado. La propuesta de cambio de un campo
    (su clon) nace pendiente y se borra al aprobarla, así que nunca lo está.
    """
    return course is not None and course.approval_status.is_approved()


def _location(course: GolfCourse) -> GeoPoint | None:
    location = course.location
    if location.latitude is None or location.longitude is None:
        return None
    return GeoPoint(latitude=location.latitude, longitude=location.longitude)


def _point(point: PointDTO) -> GeoPoint:
    try:
        return GeoPoint(latitude=point.latitude, longitude=point.longitude)
    except ValueError as e:
        raise InvalidHoleSampleError("Invalid coordinates") from e


def _dto(point: GeoPoint) -> PointDTO:
    return PointDTO(latitude=point.latitude, longitude=point.longitude)


class SubmitHoleSampleUseCase:
    """Llega la muestra de un hoyo: se guarda si es de las tres primeras y es válida."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: SubmitHoleSampleRequestDTO) -> None:
        """
        No devuelve nada, se guarde o no: quien la manda nunca nota la diferencia.

        Raises:
            GolfCourseNotFoundError: si el campo no existe o no lo ven los jugadores
            HoleNotInCourseError: si el hoyo no es del 1 al 18
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            course = await self._uow.golf_courses.find_by_id(course_id)
            if course is None or not _visible(course):
                raise GolfCourseNotFoundError(request.golf_course_id)
            # Del 1 al 18 también en un campo de 9: la segunda vuelta suele salir
            # de otras salidas, y se muestrea aparte (Agustín, 15 oct)
            if not MIN_HOLE_NUMBER <= request.hole_number <= MAX_HOLE_NUMBER:
                raise HoleNotInCourseError(request.hole_number)

            try:
                sample = HoleSample.create(
                    golf_course_id=course_id,
                    hole_number=request.hole_number,
                    tee=_point(request.tee),
                    bends=[_point(bend) for bend in request.bends],
                    green_center=_point(request.green_center),
                    course_location=_location(course),
                )
            except InvalidHoleSampleError as e:
                # Sin coordenadas en el log: solo qué regla la descartó
                logger.info(
                    "Hole sample dropped (course %s, hole %s): %s",
                    course_id,
                    request.hole_number,
                    type(e).__name__,
                )
                return

            # Contar y guardar con el hoyo bloqueado: dos que lleguen a la vez no
            # pueden ver las dos «quedan huecos» y dejar cuatro
            await self._uow.hole_samples.lock_hole(course_id, request.hole_number)
            stored = await self._uow.hole_samples.count_for_hole(course_id, request.hole_number)
            if stored >= MAX_SAMPLES_PER_HOLE:
                logger.debug(
                    "Hole sample not stored (course %s, hole %s): hole already has its samples",
                    course_id,
                    request.hole_number,
                )
                return
            await self._uow.hole_samples.add(sample)


class ListHoleSamplesUseCase:
    """De cada hoyo del 1 al 18: su primera muestra y si sigue recogiendo."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: ListHoleSamplesRequestDTO) -> list[HoleSampleStatusDTO]:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe o no lo ven los jugadores
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            if not _visible(await self._uow.golf_courses.find_by_id(course_id)):
                raise GolfCourseNotFoundError(request.golf_course_id)
            samples = await self._uow.hole_samples.list_by_course(course_id)

        by_hole: dict[int, list[HoleSample]] = {}
        for sample in samples:  # Ya vienen de la más antigua a la más nueva
            by_hole.setdefault(sample.hole_number, []).append(sample)

        statuses = []
        for number in range(MIN_HOLE_NUMBER, MAX_HOLE_NUMBER + 1):
            hole_samples = by_hole.get(number, [])
            first = hole_samples[0] if hole_samples else None
            statuses.append(
                HoleSampleStatusDTO(
                    hole_number=number,
                    first_sample=None
                    if first is None
                    else HoleSampleDTO(
                        tee=_dto(first.tee),
                        bends=[_dto(bend) for bend in first.bends],
                        green_center=_dto(first.green_center),
                    ),
                    collecting=len(hole_samples) < MAX_SAMPLES_PER_HOLE,
                )
            )
        return statuses
