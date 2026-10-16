"""
HoleSample Entity - Una muestra anónima de un hoyo (BE #532, reglas del 16 oct 2026).

Al jugar un hoyo, el móvil manda la salida, hasta dos codos (un dogleg) y el
centro del green. Sirve para cualquier hoyo, tenga o no datos en el mapa: las
muestras enriquecen los codos. **No guarda quién la mandó**: cada envío cuenta,
aunque venga de la misma persona.

Por hoyo se guardan solo las tres primeras que llegan (MAX_SAMPLES_PER_HOLE);
las demás se reciben igual y no se guardan, sin que el jugador lo note.

Los límites frenan muestras absurdas (un toque en el hoyo de al lado, o a
mitad de camino): de la salida al green entre 40 y 750 m en recta, y ningún
punto a más de 3 km del campo (si el campo tiene ubicación).
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from ..value_objects.geo_point import GeoPoint
from ..value_objects.golf_course_id import GolfCourseId
from ..value_objects.mapped_hole import MAX_HOLE_NUMBER, MIN_HOLE_NUMBER

MAX_SAMPLES_PER_HOLE = 3
MAX_BENDS = 2
MIN_TEE_TO_GREEN_M = 40.0
MAX_TEE_TO_GREEN_M = 750.0
MAX_DISTANCE_FROM_COURSE_M = 3000.0


class InvalidHoleSampleError(ValueError):
    """La muestra no vale: hoyo, puntos, codos o distancias."""


class HoleSampleOutOfRangeError(InvalidHoleSampleError):
    """De la salida al green hay menos de 40 m o más de 750 m."""


class HoleSampleFarFromCourseError(InvalidHoleSampleError):
    """Algún punto de la muestra está a más de 3 km del campo."""


def _now() -> datetime:
    """Las fechas del módulo van en UTC y sin zona."""
    return datetime.now(UTC).replace(tzinfo=None)


class HoleSample:
    """
    La muestra de un hoyo, sin autor.

    Business Rules:
    - Hoyo entero de 1 a 18 (también del 10 al 18 en un campo de 9: la segunda
      vuelta suele salir de otras salidas).
    - Salida y centro del green obligatorios; hasta 2 codos.
    - Al crearla: el green a 40-750 m de la salida en recta, y ningún punto a
      más de 3 km del campo (sin ubicación del campo, no se mira).
    """

    def __init__(
        self,
        id: UUID,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee: GeoPoint,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        created_at: datetime,
    ) -> None:
        """Comprueba la forma; las distancias se miden solo al crearla (`create`)."""
        if not isinstance(id, UUID):
            raise InvalidHoleSampleError(f"Invalid sample id {id!r}")
        if not isinstance(golf_course_id, GolfCourseId):
            raise InvalidHoleSampleError(f"Invalid golf course id {golf_course_id!r}")
        # bool es un int en Python; un 3.0 o un True no son un número de hoyo
        if (
            not isinstance(hole_number, int)
            or isinstance(hole_number, bool)
            or not MIN_HOLE_NUMBER <= hole_number <= MAX_HOLE_NUMBER
        ):
            raise InvalidHoleSampleError(f"Hole number must be 1-18, got {hole_number!r}")
        if not isinstance(tee, GeoPoint):
            raise InvalidHoleSampleError("The tee must be a GeoPoint")
        if not isinstance(green_center, GeoPoint):
            raise InvalidHoleSampleError("The green center must be a GeoPoint")
        bends = tuple(bends)
        if not all(isinstance(bend, GeoPoint) for bend in bends):
            raise InvalidHoleSampleError("Bends must be GeoPoints")
        if len(bends) > MAX_BENDS:
            raise InvalidHoleSampleError(f"At most {MAX_BENDS} bends, got {len(bends)}")

        self._id = id
        self._golf_course_id = golf_course_id
        self._hole_number = hole_number
        self._tee = tee
        self._bends = bends
        self._green_center = green_center
        self._created_at = created_at

    @classmethod
    def create(
        cls,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee: GeoPoint,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        course_location: GeoPoint | None,
    ) -> "HoleSample":
        """
        Una muestra recién llegada, con id nuevo y la hora de ahora.

        Raises:
            InvalidHoleSampleError: hoyo, puntos o codos mal formados
            HoleSampleOutOfRangeError: green a menos de 40 o más de 750 m de la salida
            HoleSampleFarFromCourseError: un punto a más de 3 km del campo
        """
        sample = cls(
            id=uuid4(),
            golf_course_id=golf_course_id,
            hole_number=hole_number,
            tee=tee,
            bends=bends,
            green_center=green_center,
            created_at=_now(),
        )
        sample._ensure_tee_to_green()
        sample._ensure_near(course_location)
        return sample

    @classmethod
    def reconstruct(
        cls,
        id: UUID,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee: GeoPoint,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        created_at: datetime,
    ) -> "HoleSample":
        """
        Una muestra leída de la BD: sin volver a medir distancias, para que una
        que se guardó válida no deje de cargarse si mañana cambian los límites.
        """
        return cls(
            id=id,
            golf_course_id=golf_course_id,
            hole_number=hole_number,
            tee=tee,
            bends=bends,
            green_center=green_center,
            created_at=created_at,
        )

    def _ensure_tee_to_green(self) -> None:
        metres = self._tee.distance_to(self._green_center)
        if not MIN_TEE_TO_GREEN_M <= metres <= MAX_TEE_TO_GREEN_M:
            raise HoleSampleOutOfRangeError(
                f"The green must be {MIN_TEE_TO_GREEN_M:.0f}-{MAX_TEE_TO_GREEN_M:.0f} m "
                f"from the tee, got {metres:.0f} m"
            )

    def _ensure_near(self, course_location: GeoPoint | None) -> None:
        if course_location is None:
            return  # Sin ubicación del campo no hay con qué comparar
        if any(
            course_location.distance_to(point) > MAX_DISTANCE_FROM_COURSE_M
            for point in self.play_line
        ):
            raise HoleSampleFarFromCourseError(
                f"Every point must be within {MAX_DISTANCE_FROM_COURSE_M:.0f} m of the course"
            )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def golf_course_id(self) -> GolfCourseId:
        return self._golf_course_id

    @property
    def hole_number(self) -> int:
        return self._hole_number

    @property
    def tee(self) -> GeoPoint:
        return self._tee

    @property
    def bends(self) -> tuple[GeoPoint, ...]:
        return self._bends

    @property
    def green_center(self) -> GeoPoint:
        return self._green_center

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def play_line(self) -> tuple[GeoPoint, ...]:
        """Salida, codos y green, en orden."""
        return (self._tee, *self._bends, self._green_center)
