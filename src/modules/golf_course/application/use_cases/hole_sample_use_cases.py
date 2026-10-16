"""
Casos de uso de las muestras anónimas de hoyo (BE #532, reglas del 16 oct 2026).

- Mandar: la barra se resuelve contra las del campo, como al anotar (una que el
  campo no tiene no se guarda). Por hoyo y barra (color y género) se guardan las tres primeras
  muestras válidas que llegan. Se responde igual y no se guarda nada si es la
  cuarta, si el dominio la rechaza (codos de más, distancias imposibles, lejos
  del campo), si su id ya está guardado (un reenvío) o si el jugador ya aportó
  otra a esa barra en los últimos 10 minutos: el jugador no debe notarlo. Vale
  para cualquier hoyo, tenga o no datos en el mapa.
- Leer: de cada hoyo, sus barras con muestra, cada una con su primera muestra y
  si sigue recogiendo. Nunca cuántas hay ni de quién son (no se guarda).
"""

import logging
from typing import TypeGuard

from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    HoleSampleDTO,
    HoleSampleStatusDTO,
    ListHoleSamplesRequestDTO,
    ListHoleSamplesResponseDTO,
    PointDTO,
    SubmitHoleSampleRequestDTO,
    SubmitHoleSampleResponseDTO,
    TeeSamplesDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleNotInCourseError,
)
from src.modules.golf_course.application.ports.recent_hole_sample_senders import (
    IRecentHoleSampleSenders,
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


def _visible(course: GolfCourse | None) -> TypeGuard[GolfCourse]:
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
    """
    Llega la muestra de un hoyo desde una barra: se guarda si es válida, si es de
    las tres primeras de esa barra, si su id es nuevo y si el jugador no aportó
    ya otra a esa barra en los últimos 10 minutos.
    """

    def __init__(
        self, uow: GolfCourseUnitOfWorkInterface, recent_senders: IRecentHoleSampleSenders
    ) -> None:
        self._uow = uow
        self._recent_senders = recent_senders

    async def execute(self, request: SubmitHoleSampleRequestDTO) -> SubmitHoleSampleResponseDTO:
        """
        La respuesta es la misma se guarde o no: quien la manda nunca nota la diferencia.

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
                if not _visible(course):
                    raise GolfCourseNotFoundError(request.golf_course_id)
                # Del 1 al 18 también en un campo de 9: la segunda vuelta suele
                # salir de otras salidas, y se muestrea aparte (Agustín, 15 oct)
                if not MIN_HOLE_NUMBER <= hole <= MAX_HOLE_NUMBER:
                    raise HoleNotInCourseError(hole)
                sample = self._sample(request, course, course_id)
                if sample is None:
                    return SubmitHoleSampleResponseDTO()
                key = (request.user_id, course_id, hole, sample.tee_color, sample.tee_gender)
                if not self._recent_senders.reserve(*key):
                    logger.debug(
                        "Hole sample not stored (course %s, hole %s): sender window",
                        course_id,
                        hole,
                    )
                    return SubmitHoleSampleResponseDTO()
                reserved = key
                stored = await self._store(sample)
            # Aquí la transacción ya se confirmó: si el commit falla, no se llega
            accepted = stored
        finally:
            # La ventana solo la gasta una muestra guardada y confirmada; si no se
            # guardó, o la transacción falló, el hueco se suelta
            if reserved is not None:
                if accepted:
                    self._recent_senders.confirm(*reserved)
                else:
                    self._recent_senders.release(*reserved)
        return SubmitHoleSampleResponseDTO()

    def _sample(
        self, request: SubmitHoleSampleRequestDTO, course: GolfCourse, course_id: GolfCourseId
    ) -> HoleSample | None:
        """
        La muestra, con la barra del campo resuelta como al anotar (`tee_for`: si
        el campo no distingue género en ese color, la barra sin género). None si
        el campo no tiene esa barra o el dominio la rechaza. En los logs, nunca
        coordenadas ni quién la manda.
        """
        hole = request.hole_number
        tee = course.tee_for(request.tee_color, request.tee_gender)
        if tee is None:
            logger.info("Hole sample dropped (course %s, hole %s): unknown tee", course_id, hole)
            return None
        try:
            return HoleSample.create(
                id=request.id,
                golf_course_id=course_id,
                hole_number=hole,
                tee_color=tee.color,
                tee_gender=tee.gender,
                tee=_point(request.tee),
                bends=[_point(bend) for bend in request.bends],
                green_center=_point(request.green_center),
                course_location=_location(course),
            )
        except InvalidHoleSampleError as e:
            logger.info(
                "Hole sample dropped (course %s, hole %s): %s", course_id, hole, type(e).__name__
            )
            return None

    async def _store(self, sample: HoleSample) -> bool:
        """
        Guarda la muestra si es nueva y su barra aún recoge. Con la barra
        bloqueada: dos que lleguen a la vez no pueden ver las dos «quedan
        huecos» y dejar cuatro.
        """
        course_id, hole = sample.golf_course_id, sample.hole_number
        tee = (sample.tee_color, sample.tee_gender)
        samples = self._uow.hole_samples
        await samples.lock_tee(course_id, hole, *tee)
        if await samples.exists(sample.id):
            logger.debug(
                "Hole sample not stored (course %s, hole %s): repeated id", course_id, hole
            )
            return False
        if await samples.count_for_tee(course_id, hole, *tee) >= MAX_SAMPLES_PER_HOLE:
            logger.debug(
                "Hole sample not stored (course %s, hole %s): tee already has its samples",
                course_id,
                hole,
            )
            return False
        # Si el mismo id entra a la vez por otra barra, gana una y la otra no cuenta
        return await samples.add(sample)


class ListHoleSamplesUseCase:
    """De cada hoyo del 1 al 18: sus barras con muestra, la primera de cada una y si recoge."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: ListHoleSamplesRequestDTO) -> ListHoleSamplesResponseDTO:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe o no lo ven los jugadores
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            if not _visible(await self._uow.golf_courses.find_by_id(course_id)):
                raise GolfCourseNotFoundError(request.golf_course_id)
            samples = await self._uow.hole_samples.list_by_course(course_id)

        # Ya vienen por hoyo y en orden de llegada: la primera vez que sale una
        # barra es su primera muestra, y así quedan ordenadas por ella
        by_hole: dict[int, dict[tuple, list[HoleSample]]] = {}
        for sample in samples:
            tees = by_hole.setdefault(sample.hole_number, {})
            tees.setdefault((sample.tee_color, sample.tee_gender), []).append(sample)

        holes = [
            HoleSampleStatusDTO(
                hole_number=number,
                tees=[
                    TeeSamplesDTO(
                        tee_color=tee_color,
                        tee_gender=tee_gender,
                        first_sample=HoleSampleDTO(
                            tee=_dto(tee_samples[0].tee),
                            bends=[_dto(bend) for bend in tee_samples[0].bends],
                            green_center=_dto(tee_samples[0].green_center),
                        ),
                        collecting=len(tee_samples) < MAX_SAMPLES_PER_HOLE,
                    )
                    for (tee_color, tee_gender), tee_samples in by_hole.get(number, {}).items()
                ],
            )
            for number in range(MIN_HOLE_NUMBER, MAX_HOLE_NUMBER + 1)
        ]
        return ListHoleSamplesResponseDTO(holes=holes)
