"""
Casos de uso de las marcas de hoyo de los jugadores (BE #532, PR C).

Lo que se le pide al jugador depende de lo que el hoyo ya tenga en el mapa
APROBADO (uno pendiente o rechazado no lo ven, así que no cuenta):
- sin salida: salida, hasta dos codos y el centro del green;
- con salida y sin green: solo el green, medido desde esa salida;
- con salida y green: nada, el hoyo ya está mapeado.
"""

from src.modules.golf_course.application.dtos.hole_mark_dtos import (
    HoleMarkDTO,
    ListMyHoleMarksRequestDTO,
    PointDTO,
    SaveHoleMarkRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleAlreadyHasTeeError,
    HoleAlreadyMappedError,
    HoleNotInCourseError,
    TeeRequiredError,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole_mark import (
    HoleMark,
    InvalidHoleMarkError,
    ensure_near_course,
    ensure_tee_to_green,
)
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus
from src.modules.golf_course.domain.value_objects.mapped_hole import MAX_HOLE_NUMBER, MappedHole
from src.modules.user.domain.value_objects.user_id import UserId


def _point(point: PointDTO) -> GeoPoint:
    try:
        return GeoPoint(latitude=point.latitude, longitude=point.longitude)
    except ValueError as e:
        raise InvalidHoleMarkError("Invalid coordinates") from e


def _to_dto(mark: HoleMark) -> HoleMarkDTO:
    def dto(point: GeoPoint) -> PointDTO:
        return PointDTO(latitude=point.latitude, longitude=point.longitude)

    return HoleMarkDTO(
        hole_number=mark.hole_number,
        tee=dto(mark.tee) if mark.tee is not None else None,
        bends=[dto(bend) for bend in mark.bends],
        green_center=dto(mark.green_center),
        marked_at=mark.updated_at,
    )


def _location(course: GolfCourse) -> GeoPoint | None:
    location = course.location
    if location.latitude is None or location.longitude is None:
        return None
    return GeoPoint(latitude=location.latitude, longitude=location.longitude)


class SaveHoleMarkUseCase:
    """Un jugador marca un hoyo, o lo vuelve a marcar (sustituye su marca)."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def _approved_hole(self, course_id: GolfCourseId, number: int) -> MappedHole | None:
        hole_map = await self._uow.hole_maps.find_by_golf_course_id(course_id)
        if hole_map is None or hole_map.status is not HoleMapStatus.APPROVED:
            return None
        return next((hole for hole in hole_map.holes if hole.number == number), None)

    async def execute(self, request: SaveHoleMarkRequestDTO) -> HoleMarkDTO:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe
            HoleNotInCourseError: si el campo no tiene ese hoyo
            HoleAlreadyMappedError: si el hoyo ya tiene salida y green aprobados
            HoleAlreadyHasTeeError: si el hoyo ya tiene salida y la marca trae otra
            TeeRequiredError: si el hoyo no tiene salida y la marca no la trae
            InvalidHoleMarkError: (del dominio) coordenadas o codos imposibles
            HoleMarkOutOfRangeError: (del dominio) green a menos de 40 o más de 750 m
            HoleMarkFarFromCourseError: (del dominio) un punto a más de 3 km del campo
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            course = await self._uow.golf_courses.find_by_id(course_id)
            if course is None:
                raise GolfCourseNotFoundError(request.golf_course_id)
            if not 1 <= request.hole_number <= (course.physical_holes or MAX_HOLE_NUMBER):
                raise HoleNotInCourseError(request.hole_number)

            tee = _point(request.tee) if request.tee is not None else None
            green_center = _point(request.green_center)
            mapped = await self._approved_hole(course_id, request.hole_number)
            if mapped is not None and mapped.green is not None:
                raise HoleAlreadyMappedError(request.hole_number)
            if mapped is not None:
                if tee is not None:
                    raise HoleAlreadyHasTeeError(request.hole_number)
                ensure_tee_to_green(mapped.tee, green_center)
            elif tee is None:
                raise TeeRequiredError(request.hole_number)

            mark = HoleMark.create(
                golf_course_id=course_id,
                hole_number=request.hole_number,
                user_id=UserId(request.user_id),
                tee=tee,
                bends=[_point(bend) for bend in request.bends],
                green_center=green_center,
            )
            ensure_near_course(mark, _location(course))
            await self._uow.hole_marks.save(mark)
            return _to_dto(mark)


class ListMyHoleMarksUseCase:
    """Las marcas del jugador en un campo, por orden de hoyo."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: ListMyHoleMarksRequestDTO) -> list[HoleMarkDTO]:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            if await self._uow.golf_courses.find_by_id(course_id) is None:
                raise GolfCourseNotFoundError(request.golf_course_id)
            marks = await self._uow.hole_marks.find_by_course_and_user(
                course_id, UserId(request.user_id)
            )
            return [_to_dto(mark) for mark in marks]
