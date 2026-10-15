"""
HoleMark Entity - Un hoyo marcado por un jugador (BE #532, PR C).

En un hoyo sin datos el jugador toca la salida y el centro del green, y en un
dogleg arrastra hasta dos codos; si el hoyo ya tiene salida, solo marca el
green. La marca es suya y hay una por jugador y hoyo: volver a marcar la
sustituye, salvo que la que llega sea más vieja que la guardada (una que se
quedó en la cola del móvil sin cobertura). La ve él al momento; los demás, cuando un admin la apruebe y pase al
mapa con origen PLAYER.

Los límites frenan marcas absurdas (un toque en el hoyo de al lado, o a mitad
de camino): de la salida al green entre 40 y 750 m en recta, y ningún punto a
más de 3 km del campo.
"""

from collections.abc import Iterable
from datetime import UTC, datetime

from src.modules.user.domain.value_objects.user_id import UserId

from ..value_objects.geo_point import GeoPoint
from ..value_objects.golf_course_id import GolfCourseId
from ..value_objects.mapped_hole import MAX_HOLE_NUMBER, MIN_HOLE_NUMBER

MAX_BENDS = 2
MIN_TEE_TO_GREEN_M = 40.0
MAX_TEE_TO_GREEN_M = 750.0
MAX_DISTANCE_FROM_COURSE_M = 3000.0


class InvalidHoleMarkError(ValueError):
    """La marca está mal formada: hoyo, puntos o codos."""


class HoleMarkOutOfRangeError(ValueError):
    """De la salida al green hay menos de 40 m o más de 750 m."""


class HoleMarkFarFromCourseError(ValueError):
    """Algún punto de la marca está a más de 3 km del campo."""


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _naive_utc(moment: datetime) -> datetime:
    """Las fechas del módulo van en UTC y sin zona; una sin zona ya se toma por UTC."""
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


def ensure_tee_to_green(tee: GeoPoint, green_center: GeoPoint) -> None:
    """
    Raises:
        HoleMarkOutOfRangeError: si la recta de la salida al green se sale de 40-750 m
    """
    metres = tee.distance_to(green_center)
    if not MIN_TEE_TO_GREEN_M <= metres <= MAX_TEE_TO_GREEN_M:
        raise HoleMarkOutOfRangeError(
            f"The green must be {MIN_TEE_TO_GREEN_M:.0f}-{MAX_TEE_TO_GREEN_M:.0f} m "
            f"from the tee, got {metres:.0f} m"
        )


def ensure_near_course(mark: "HoleMark", course_location: GeoPoint | None) -> None:
    """
    Sin ubicación del campo no hay con qué comparar, y no se comprueba.

    Raises:
        HoleMarkFarFromCourseError: si algún punto está a más de 3 km del campo
    """
    if course_location is None:
        return
    points = mark.play_line or (mark.green_center,)
    if any(course_location.distance_to(p) > MAX_DISTANCE_FROM_COURSE_M for p in points):
        raise HoleMarkFarFromCourseError(
            f"Every point must be within {MAX_DISTANCE_FROM_COURSE_M:.0f} m of the course"
        )


class HoleMark:
    """
    La marca de un jugador en un hoyo.

    Business Rules:
    - Hoyo entero de 1 a 18.
    - El centro del green es obligatorio; la salida, no (el hoyo ya la tenía).
    - Hasta 2 codos, y solo con salida: sin ella no hay línea propia que doblar.
    - Con salida, el green a 40-750 m de ella en recta.
    """

    def __init__(
        self,
        golf_course_id: GolfCourseId,
        hole_number: int,
        user_id: UserId,
        tee: GeoPoint | None,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        if not isinstance(golf_course_id, GolfCourseId):
            raise InvalidHoleMarkError(f"Invalid golf course id {golf_course_id!r}")
        if not isinstance(user_id, UserId):
            raise InvalidHoleMarkError(f"Invalid user id {user_id!r}")
        # bool es un int en Python; un 3.0 o un True no son un número de hoyo
        if (
            not isinstance(hole_number, int)
            or isinstance(hole_number, bool)
            or not MIN_HOLE_NUMBER <= hole_number <= MAX_HOLE_NUMBER
        ):
            raise InvalidHoleMarkError(f"Hole number must be 1-18, got {hole_number!r}")
        if not isinstance(green_center, GeoPoint):
            raise InvalidHoleMarkError("The green center must be a GeoPoint")
        if tee is not None and not isinstance(tee, GeoPoint):
            raise InvalidHoleMarkError("The tee must be a GeoPoint")
        bends = tuple(bends)
        if not all(isinstance(bend, GeoPoint) for bend in bends):
            raise InvalidHoleMarkError("Bends must be GeoPoints")
        if len(bends) > MAX_BENDS:
            raise InvalidHoleMarkError(f"At most {MAX_BENDS} bends, got {len(bends)}")
        if bends and tee is None:
            raise InvalidHoleMarkError("Bends need a tee")
        if tee is not None:
            ensure_tee_to_green(tee, green_center)

        self._golf_course_id = golf_course_id
        self._hole_number = hole_number
        self._user_id = user_id
        self._tee = tee
        self._bends = bends
        self._green_center = green_center
        self._created_at = created_at
        self._updated_at = updated_at

    @classmethod
    def create(
        cls,
        golf_course_id: GolfCourseId,
        hole_number: int,
        user_id: UserId,
        green_center: GeoPoint,
        tee: GeoPoint | None = None,
        bends: Iterable[GeoPoint] = (),
        marked_at: datetime | None = None,
    ) -> "HoleMark":
        """
        Una marca recién hecha. `marked_at` es cuándo la hizo el jugador, que
        llega tarde si se marcó sin cobertura; nunca después de ahora (un reloj
        adelantado no puede ganar a todas las que vengan detrás).
        """
        now = _now()
        if marked_at is not None:
            now = min(_naive_utc(marked_at), now)
        return cls(
            golf_course_id=golf_course_id,
            hole_number=hole_number,
            user_id=user_id,
            tee=tee,
            bends=bends,
            green_center=green_center,
            created_at=now,
            updated_at=now,
        )

    @property
    def golf_course_id(self) -> GolfCourseId:
        return self._golf_course_id

    @property
    def hole_number(self) -> int:
        return self._hole_number

    @property
    def user_id(self) -> UserId:
        return self._user_id

    @property
    def tee(self) -> GeoPoint | None:
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
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def play_line(self) -> tuple[GeoPoint, ...]:
        """Salida, codos y green; vacía si la marca es solo del green."""
        if self._tee is None:
            return ()
        return (self._tee, *self._bends, self._green_center)
