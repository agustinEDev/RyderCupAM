"""
Casos de uso de las muestras anónimas de hoyo (BE #532, reglas del 16 oct 2026).

- Mandar: la barra se resuelve contra las del campo, como al anotar (una que el
  campo no tiene no se guarda), y se guarda con la muestra. Por hoyo se guardan
  las tres primeras muestras válidas que llegan, de cualquier barra (17 oct:
  una referencia por hoyo). Se responde igual y no se guarda nada si es la
  cuarta, si el dominio la rechaza (codos de más, distancias imposibles, lejos
  del campo), si su id ya está guardado (un reenvío), si el jugador ya aportó
  otra a ese hoyo en los últimos 10 minutos, o si el mapa de OSM aprobado ya
  trae el hoyo con línea y green (17 oct: con lo de OSM basta): el jugador no
  debe notarlo. Una muestra puede ser solo green (sin salida ni codos), y de
  esas, una por hoyo.
- Leer: de cada hoyo, su primera muestra completa, el green de su primera
  muestra solo green y si sigue recogiendo; y, para los móviles de antes, sus
  barras con muestra completa. Nunca cuántas hay ni de quién son.
"""

import logging

from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    HoleSampleDTO,
    HoleSampleStatusDTO,
    ListHoleSamplesRequestDTO,
    ListHoleSamplesResponseDTO,
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
from src.modules.golf_course.application.use_cases.hole_points import (
    line_dto,
    location_of,
    point_dto,
    to_point,
    visible,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole_sample import (
    MAX_SAMPLES_PER_HOLE,
    HoleSample,
    InvalidHoleSampleError,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus
from src.modules.golf_course.domain.value_objects.mapped_hole import (
    MAX_HOLE_NUMBER,
    MIN_HOLE_NUMBER,
)

logger = logging.getLogger(__name__)


def _mapped(hole_map: CourseHoleMap | None, hole: int) -> bool:
    """
    Si el mapa de OSM aprobado ya trae el hoyo con línea y green: entonces no
    recoge muestras (Agustín, 17 oct). Un hoyo que el mapa no trae, o sin green,
    se completa con ellas.
    """
    if hole_map is None or hole_map.status is not HoleMapStatus.APPROVED:
        return False
    mapped = hole_map.hole(hole)
    # Un hoyo del mapa siempre trae línea (al menos dos puntos); falta el green o no
    return mapped is not None and not mapped.needs_green


class SubmitHoleSampleUseCase:
    """
    Llega la muestra de un hoyo desde una barra: se guarda si es válida, si es de
    las tres primeras del hoyo, si su id es nuevo, si el jugador no aportó ya otra
    a ese hoyo en los últimos 10 minutos y si el hoyo no está ya en el mapa de OSM.
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
                if not visible(course):
                    raise GolfCourseNotFoundError(request.golf_course_id)
                # Del 1 al 18 también en un campo de 9: la segunda vuelta suele
                # salir de otras salidas, y se muestrea aparte (Agustín, 15 oct)
                if not MIN_HOLE_NUMBER <= hole <= MAX_HOLE_NUMBER:
                    raise HoleNotInCourseError(hole)
                sample = self._sample(request, course, course_id)
                if sample is None:
                    return SubmitHoleSampleResponseDTO()
                key = (request.user_id, course_id, hole)
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
                tee=to_point(request.tee, InvalidHoleSampleError)
                if request.tee is not None
                else None,
                bends=[to_point(bend, InvalidHoleSampleError) for bend in request.bends],
                green_center=to_point(request.green_center, InvalidHoleSampleError),
                course_location=location_of(course),
            )
        except InvalidHoleSampleError as e:
            logger.info(
                "Hole sample dropped (course %s, hole %s): %s", course_id, hole, type(e).__name__
            )
            return None

    async def _store(self, sample: HoleSample) -> bool:
        """
        Guarda la muestra si es nueva y su hoyo aún recoge. Con el hoyo
        bloqueado: dos que lleguen a la vez no pueden ver las dos «quedan
        huecos» y dejar cuatro.
        """
        course_id, hole = sample.golf_course_id, sample.hole_number
        samples = self._uow.hole_samples
        await samples.lock_hole(course_id, hole)
        # Con el hoyo ya bloqueado, y tras lo que se mira sin la BD (la muestra,
        # la ventana del jugador): el mapa de OSM aprobado ya lo trae (17 oct)
        if _mapped(await self._uow.hole_maps.find_by_golf_course_id(course_id), hole):
            logger.debug(
                "Hole sample not stored (course %s, hole %s): mapped hole", course_id, hole
            )
            return False
        # Con su línea guardada por el admin, el hoyo ya no recoge (BE #575)
        if await self._uow.saved_holes.get(course_id, hole) is not None:
            logger.debug("Hole sample not stored (course %s, hole %s): saved hole", course_id, hole)
            return False
        if await samples.exists(sample.id):
            logger.debug(
                "Hole sample not stored (course %s, hole %s): repeated id", course_id, hole
            )
            return False
        # Una solo green por hoyo, la única que se lee: tres a mitad de hoyo
        # dejarían el hoyo lleno sin que nadie pudiera completarlo (17 oct)
        if sample.is_green_only and await samples.has_green_only(course_id, hole):
            logger.debug(
                "Hole sample not stored (course %s, hole %s): hole already has its green",
                course_id,
                hole,
            )
            return False
        if await samples.count_for_hole(course_id, hole) >= MAX_SAMPLES_PER_HOLE:
            logger.debug(
                "Hole sample not stored (course %s, hole %s): hole already has its samples",
                course_id,
                hole,
            )
            return False
        # Si el mismo id entra a la vez por otro hoyo, gana uno y el otro no cuenta
        return await samples.add(sample)


def _sample_dto(sample: HoleSample) -> HoleSampleDTO:
    """Una muestra completa (con salida); las solo green van por `first_green`."""
    if sample.tee is None:
        raise ValueError("A green-only sample is not a full sample")
    return line_dto(sample.tee, sample.bends, sample.green_center)


class ListHoleSamplesUseCase:
    """
    De cada hoyo del 1 al 18: su primera muestra completa, el green de la primera
    solo green y si recoge; y sus barras con muestra completa (móviles de antes).
    """

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: ListHoleSamplesRequestDTO) -> ListHoleSamplesResponseDTO:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe o no lo ven los jugadores
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            if not visible(await self._uow.golf_courses.find_by_id(course_id)):
                raise GolfCourseNotFoundError(request.golf_course_id)
            samples = await self._uow.hole_samples.list_by_course(course_id)
            hole_map = await self._uow.hole_maps.find_by_golf_course_id(course_id)
            saved = {
                h.hole_number: h for h in await self._uow.saved_holes.list_by_course(course_id)
            }

        # Ya vienen por hoyo y en orden de llegada
        by_hole: dict[int, list[HoleSample]] = {}
        for sample in samples:
            by_hole.setdefault(sample.hole_number, []).append(sample)

        holes = []
        for number in range(MIN_HOLE_NUMBER, MAX_HOLE_NUMBER + 1):
            hole_samples = by_hole.get(number, [])
            complete = [x for x in hole_samples if not x.is_green_only]
            loose = [x for x in hole_samples if x.is_green_only]
            saved_hole = saved.get(number)
            collecting = (
                len(hole_samples) < MAX_SAMPLES_PER_HOLE
                and saved_hole is None
                and not _mapped(hole_map, number)
            )
            # La primera vez que sale una barra es su primera muestra completa
            tees: dict[tuple, HoleSample] = {}
            for sample in complete:
                tees.setdefault((sample.tee_color, sample.tee_gender), sample)
            holes.append(
                HoleSampleStatusDTO(
                    hole_number=number,
                    saved_line=(
                        line_dto(saved_hole.tee, saved_hole.bends, saved_hole.green_center)
                        if saved_hole
                        else None
                    ),
                    first_sample=_sample_dto(complete[0]) if complete else None,
                    first_green=point_dto(loose[0].green_center) if loose else None,
                    collecting=collecting,
                    tees=[
                        TeeSamplesDTO(
                            tee_color=tee_color,
                            tee_gender=tee_gender,
                            first_sample=_sample_dto(first),
                            collecting=collecting,
                        )
                        for (tee_color, tee_gender), first in tees.items()
                    ],
                )
            )
        return ListHoleSamplesResponseDTO(holes=holes)
