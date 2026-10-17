"""
HoleSample Entity - Una muestra anónima de un hoyo (BE #532, reglas del 16 oct 2026).

Al jugar un hoyo, el móvil manda la salida, hasta dos codos (un dogleg) y el
centro del green, y desde qué barra (color y género: cada una sale de un sitio
distinto). Sirve para cualquier hoyo, tenga o no datos en el mapa: las
muestras enriquecen los codos. **No guarda quién la mandó**, y de cuándo llegó
solo el día (UTC): la hora ayudaría a saber quién estaba en el campo. El id lo
genera el móvil, para que un reenvío cuente una vez, y no dice nada de quién.

Por hoyo se guardan solo las tres primeras que llegan, de cualquier barra
(MAX_SAMPLES_PER_HOLE; Agustín, 17 oct: una referencia por hoyo); las demás se
reciben igual y no se guardan, sin que el jugador lo note.

Una muestra puede ser **solo green** (17 oct): quien abre el mapa a mitad de
hoyo no está en la salida y marca solo el green, sin codos; el siguiente que
esté en la salida completa el hoyo con él.

Los límites frenan muestras absurdas (un toque en el hoyo de al lado, o a
mitad de camino): de la salida al green entre 40 y 750 m en recta, y ningún
punto a más de 3 km del campo (si el campo tiene ubicación).
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from uuid import UUID

from src.shared.domain.value_objects.gender import Gender

from ..value_objects.geo_point import GeoPoint
from ..value_objects.golf_course_id import GolfCourseId
from ..value_objects.mapped_hole import MAX_HOLE_NUMBER, MIN_HOLE_NUMBER
from ..value_objects.tee_color import TeeColor

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


def play_line_problem(
    tee: GeoPoint | None,
    green_center: GeoPoint,
    points: Iterable[GeoPoint],
    course_location: GeoPoint | None,
) -> str | None:
    """
    Lo que hace imposible una línea de hoyo, o None si vale: con salida, el green
    a 40-750 m de ella en recta; y ningún punto a más de 3 km del campo (sin su
    ubicación, no se mira). La misma regla para una muestra y para la línea que
    guarda el admin (BE #575).
    """
    if tee is not None:
        metres = tee.distance_to(green_center)
        if not MIN_TEE_TO_GREEN_M <= metres <= MAX_TEE_TO_GREEN_M:
            return (
                f"The green must be {MIN_TEE_TO_GREEN_M:.0f}-{MAX_TEE_TO_GREEN_M:.0f} m "
                f"from the tee, got {metres:.0f} m"
            )
    if course_location is not None and any(
        course_location.distance_to(point) > MAX_DISTANCE_FROM_COURSE_M for point in points
    ):
        return f"Every point must be within {MAX_DISTANCE_FROM_COURSE_M:.0f} m of the course"
    return None


def _today() -> date:
    """El día de hoy en UTC: de la llegada no se guarda más."""
    return datetime.now(UTC).date()


class HoleSample:
    """
    La muestra de un hoyo desde una barra, sin autor y sin hora.

    Business Rules:
    - El id es un UUID (lo genera el móvil).
    - La barra es un color (TeeColor) y un género (Gender, o None si la barra no
      lo tiene).
    - Hoyo entero de 1 a 18 (también del 10 al 18 en un campo de 9: la segunda
      vuelta suele salir de otras salidas).
    - Centro del green obligatorio. Con salida, hasta 2 codos; sin salida (solo
      green), ninguno.
    - Al crearla: con salida, el green a 40-750 m de ella en recta; y ningún
      punto a más de 3 km del campo (sin ubicación del campo, no se mira).
    """

    def __init__(
        self,
        id: UUID,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
        tee: GeoPoint | None,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        received_on: date,
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
        if not isinstance(tee_color, TeeColor):
            raise InvalidHoleSampleError(f"Invalid tee color {tee_color!r}")
        if tee_gender is not None and not isinstance(tee_gender, Gender):
            raise InvalidHoleSampleError(f"Invalid tee gender {tee_gender!r}")
        # Un datetime también es un date: con él se colaría la hora
        if not isinstance(received_on, date) or isinstance(received_on, datetime):
            raise InvalidHoleSampleError("The arrival must be a day, without time")
        if tee is not None and not isinstance(tee, GeoPoint):
            raise InvalidHoleSampleError("The tee must be a GeoPoint")
        if not isinstance(green_center, GeoPoint):
            raise InvalidHoleSampleError("The green center must be a GeoPoint")
        bends = tuple(bends)
        if not all(isinstance(bend, GeoPoint) for bend in bends):
            raise InvalidHoleSampleError("Bends must be GeoPoints")
        if len(bends) > MAX_BENDS:
            raise InvalidHoleSampleError(f"At most {MAX_BENDS} bends, got {len(bends)}")
        if tee is None and bends:
            raise InvalidHoleSampleError("A green-only sample has no bends")

        self._id = id
        self._golf_course_id = golf_course_id
        self._hole_number = hole_number
        self._tee_color = tee_color
        self._tee_gender = tee_gender
        self._tee = tee
        self._bends = bends
        self._green_center = green_center
        self._received_on = received_on

    @classmethod
    def create(
        cls,
        id: UUID,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee_color: TeeColor,
        tee_gender: Gender | None,
        tee: GeoPoint | None,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        course_location: GeoPoint | None,
    ) -> "HoleSample":
        """
        Una muestra recién llegada, con el id que puso el móvil y el día de hoy.

        Raises:
            InvalidHoleSampleError: hoyo, puntos o codos mal formados
            HoleSampleOutOfRangeError: green a menos de 40 o más de 750 m de la salida
            HoleSampleFarFromCourseError: un punto a más de 3 km del campo
        """
        sample = cls(
            id=id,
            golf_course_id=golf_course_id,
            hole_number=hole_number,
            tee_color=tee_color,
            tee_gender=tee_gender,
            tee=tee,
            bends=bends,
            green_center=green_center,
            received_on=_today(),
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
        tee_color: TeeColor,
        tee_gender: Gender | None,
        tee: GeoPoint | None,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        received_on: date,
    ) -> "HoleSample":
        """
        Una muestra leída de la BD: sin volver a medir distancias, para que una
        que se guardó válida no deje de cargarse si mañana cambian los límites.
        """
        return cls(
            id=id,
            golf_course_id=golf_course_id,
            hole_number=hole_number,
            tee_color=tee_color,
            tee_gender=tee_gender,
            tee=tee,
            bends=bends,
            green_center=green_center,
            received_on=received_on,
        )

    def _ensure_tee_to_green(self) -> None:
        problem = play_line_problem(self._tee, self._green_center, (), None)
        if problem:
            raise HoleSampleOutOfRangeError(problem)

    def _ensure_near(self, course_location: GeoPoint | None) -> None:
        problem = play_line_problem(None, self._green_center, self.play_line, course_location)
        if problem:
            raise HoleSampleFarFromCourseError(problem)

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
    def tee_color(self) -> TeeColor:
        return self._tee_color

    @property
    def tee_gender(self) -> Gender | None:
        return self._tee_gender

    @property
    def tee(self) -> GeoPoint | None:
        """None en una muestra solo green."""
        return self._tee

    @property
    def is_green_only(self) -> bool:
        """Si es una muestra solo green: sin salida ni codos (17 oct)."""
        return self._tee is None

    @property
    def bends(self) -> tuple[GeoPoint, ...]:
        return self._bends

    @property
    def green_center(self) -> GeoPoint:
        return self._green_center

    @property
    def received_on(self) -> date:
        """El día (UTC) en que llegó; sin hora a propósito."""
        return self._received_on

    @property
    def play_line(self) -> tuple[GeoPoint, ...]:
        """Salida, codos y green, en orden; solo el green en una muestra solo green."""
        if self._tee is None:
            return (self._green_center,)
        return (self._tee, *self._bends, self._green_center)
