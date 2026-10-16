"""
Casos de uso del admin con las líneas de los hoyos (BE #575, 17 oct 2026).

Una referencia por hoyo (Agustín, 17 oct): el admin, a partir de las muestras,
guarda la línea de cada hoyo (la que ven todos los jugadores, y con ella el hoyo
deja de recoger muestras), la puede volver a guardar encima o reabrir el hoyo
(se quita, y vuelve a recoger), y puede borrar una muestra mala (deja libre su
hueco). Que quien llama es admin lo mira la ruta.
"""

from src.modules.golf_course.application.dtos.hole_sample_dtos import PointDTO
from src.modules.golf_course.application.dtos.saved_hole_dtos import (
    DeleteHoleSampleRequestDTO,
    ReopenHoleRequestDTO,
    SavedHoleLineDTO,
    SaveHoleLineRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleNotInCourseError,
    HoleSampleNotFoundError,
    InvalidHoleLineError,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.saved_hole import InvalidSavedHoleError, SavedHole
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.mapped_hole import (
    MAX_HOLE_NUMBER,
    MIN_HOLE_NUMBER,
)
from src.modules.user.domain.value_objects.user_id import UserId


def _ensure_hole(hole_number: int) -> None:
    if not MIN_HOLE_NUMBER <= hole_number <= MAX_HOLE_NUMBER:
        raise HoleNotInCourseError(hole_number)


def _location(course: GolfCourse) -> GeoPoint | None:
    location = course.location
    if location.latitude is None or location.longitude is None:
        return None
    return GeoPoint(latitude=location.latitude, longitude=location.longitude)


def _point(point: PointDTO) -> GeoPoint:
    try:
        return GeoPoint(latitude=point.latitude, longitude=point.longitude)
    except ValueError as e:
        raise InvalidHoleLineError("Invalid coordinates") from e


def _dto(point: GeoPoint) -> PointDTO:
    return PointDTO(latitude=point.latitude, longitude=point.longitude)


def saved_line_dto(hole: SavedHole) -> SavedHoleLineDTO:
    """La línea guardada, como la lee el móvil (como una muestra completa)."""
    return SavedHoleLineDTO(
        tee=_dto(hole.tee),
        bends=[_dto(bend) for bend in hole.bends],
        green_center=_dto(hole.green_center),
    )


class SaveHoleLineUseCase:
    """Guarda (o vuelve a guardar encima) la línea de referencia de un hoyo."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: SaveHoleLineRequestDTO) -> SavedHoleLineDTO:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe
            HoleNotInCourseError: si el hoyo no es del 1 al 18
            InvalidHoleLineError: codos de más, green a menos de 40 o más de 750 m,
                un punto a más de 3 km del campo o coordenadas imposibles
        """
        _ensure_hole(request.hole_number)
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            course = await self._uow.golf_courses.find_by_id(course_id)
            if course is None:
                raise GolfCourseNotFoundError(request.golf_course_id)
            try:
                hole = SavedHole.create(
                    golf_course_id=course_id,
                    hole_number=request.hole_number,
                    tee=_point(request.tee),
                    bends=[_point(bend) for bend in request.bends],
                    green_center=_point(request.green_center),
                    saved_by=UserId(request.admin_id),
                    course_location=_location(course),
                )
            except InvalidSavedHoleError as e:
                raise InvalidHoleLineError(str(e)) from e
            await self._uow.saved_holes.save(hole)
        return saved_line_dto(hole)


class ReopenHoleUseCase:
    """Quita la línea de un hoyo: vuelve a recoger muestras. Sin línea, nada."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: ReopenHoleRequestDTO) -> None:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe
            HoleNotInCourseError: si el hoyo no es del 1 al 18
        """
        _ensure_hole(request.hole_number)
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            if await self._uow.golf_courses.find_by_id(course_id) is None:
                raise GolfCourseNotFoundError(request.golf_course_id)
            await self._uow.saved_holes.delete(course_id, request.hole_number)


class DeleteHoleSampleUseCase:
    """Borra una muestra mala de un campo: deja libre su hueco en el hoyo."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: DeleteHoleSampleRequestDTO) -> None:
        """
        Raises:
            HoleSampleNotFoundError: si la muestra no está en ese campo
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            if not await self._uow.hole_samples.delete(course_id, request.sample_id):
                raise HoleSampleNotFoundError(str(request.sample_id))
