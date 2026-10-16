"""
Casos de uso del admin con las líneas de los hoyos (BE #575, 17 oct 2026).

Una referencia por hoyo (Agustín, 17 oct): el admin, a partir de las muestras,
guarda la línea de cada hoyo (la que ven todos los jugadores, y con ella el hoyo
deja de recoger muestras), la puede volver a guardar encima o reabrir el hoyo
(se quita, y vuelve a recoger), y puede borrar una muestra mala (deja libre su
hueco). Que quien llama es admin lo mira la ruta.
"""

from src.modules.golf_course.application.dtos.hole_sample_dtos import HoleSampleDTO
from src.modules.golf_course.application.dtos.saved_hole_dtos import (
    DeleteHoleSampleRequestDTO,
    ReopenHoleRequestDTO,
    SaveHoleLineRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleNotInCourseError,
    HoleSampleNotFoundError,
    InvalidHoleLineError,
)
from src.modules.golf_course.application.use_cases.hole_points import (
    line_dto,
    location_of,
    to_point,
    visible,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.saved_hole import InvalidSavedHoleError, SavedHole
from src.modules.golf_course.domain.repositories.golf_course_unit_of_work_interface import (
    GolfCourseUnitOfWorkInterface,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.mapped_hole import (
    MAX_HOLE_NUMBER,
    MIN_HOLE_NUMBER,
)
from src.modules.user.domain.value_objects.user_id import UserId


def _ensure_hole(hole_number: int) -> None:
    if not MIN_HOLE_NUMBER <= hole_number <= MAX_HOLE_NUMBER:
        raise HoleNotInCourseError(hole_number)


def saved_line_dto(hole: SavedHole) -> HoleSampleDTO:
    """La línea guardada, como la lee el móvil (como una muestra completa)."""
    return line_dto(hole.tee, hole.bends, hole.green_center)


async def _visible_course(uow: GolfCourseUnitOfWorkInterface, golf_course_id: str) -> GolfCourse:
    """
    El campo, si lo ven los jugadores. Uno pendiente, o la propuesta de cambio de
    otro (su clon), no lleva líneas: nadie las vería y se irían con él (revisión).
    """
    course = await uow.golf_courses.find_by_id(GolfCourseId(golf_course_id))
    if not visible(course):
        raise GolfCourseNotFoundError(golf_course_id)
    return course


class SaveHoleLineUseCase:
    """Guarda (o vuelve a guardar encima) la línea de referencia de un hoyo."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: SaveHoleLineRequestDTO) -> HoleSampleDTO:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe o no lo ven los jugadores
            HoleNotInCourseError: si el hoyo no es del 1 al 18
            InvalidHoleLineError: codos de más, green a menos de 40 o más de 750 m,
                un punto a más de 3 km del campo o coordenadas imposibles
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            course = await _visible_course(self._uow, request.golf_course_id)
            _ensure_hole(request.hole_number)
            try:
                hole = SavedHole.create(
                    golf_course_id=course_id,
                    hole_number=request.hole_number,
                    tee=to_point(request.tee, InvalidHoleLineError),
                    bends=[to_point(bend, InvalidHoleLineError) for bend in request.bends],
                    green_center=to_point(request.green_center, InvalidHoleLineError),
                    saved_by=UserId(request.admin_id),
                    course_location=location_of(course),
                )
            except InvalidSavedHoleError as e:
                raise InvalidHoleLineError(str(e)) from e
            # Como al mandar una muestra: con el hoyo bloqueado, un envío a la vez
            # no se guarda detrás de la línea
            await self._uow.hole_samples.lock_hole(course_id, request.hole_number)
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
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            await _visible_course(self._uow, request.golf_course_id)
            _ensure_hole(request.hole_number)
            await self._uow.hole_samples.lock_hole(course_id, request.hole_number)
            await self._uow.saved_holes.delete(course_id, request.hole_number)


class DeleteHoleSampleUseCase:
    """Borra una muestra mala de un campo: deja libre su hueco en el hoyo."""

    def __init__(self, uow: GolfCourseUnitOfWorkInterface) -> None:
        self._uow = uow

    async def execute(self, request: DeleteHoleSampleRequestDTO) -> None:
        """
        Raises:
            GolfCourseNotFoundError: si el campo no existe
            HoleSampleNotFoundError: si la muestra no está en ese campo
        """
        course_id = GolfCourseId(request.golf_course_id)
        async with self._uow:
            if await self._uow.golf_courses.find_by_id(course_id) is None:
                raise GolfCourseNotFoundError(request.golf_course_id)
            if not await self._uow.hole_samples.delete(course_id, request.sample_id):
                raise HoleSampleNotFoundError(str(request.sample_id))
