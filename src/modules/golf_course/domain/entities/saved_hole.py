"""
SavedHole Entity - La línea que el admin guarda de un hoyo (BE #575, 17 oct 2026).

Una referencia por hoyo (Agustín, 17 oct): de la salida al centro del green, con
hasta dos codos, que ven todos los jugadores, de la barra que sean. El admin la
hace a partir de las muestras (o de la línea de OSM) y, guardada, el hoyo ya no
recoge muestras. Se puede volver a guardar encima, y reabrir el hoyo la quita.

Las mismas reglas que una muestra completa (`HoleSample`): de la salida al green
entre 40 y 750 m en recta, y ningún punto a más de 3 km del campo.
"""

from collections.abc import Iterable
from datetime import UTC, datetime

from src.modules.user.domain.value_objects.user_id import UserId

from ..value_objects.geo_point import GeoPoint
from ..value_objects.golf_course_id import GolfCourseId
from ..value_objects.mapped_hole import MAX_HOLE_NUMBER, MIN_HOLE_NUMBER
from .hole_sample import MAX_BENDS, play_line_problem


class InvalidSavedHoleError(ValueError):
    """La línea no vale: hoyo, puntos, codos o distancias."""


class SavedHole:
    """La línea de referencia de un hoyo, guardada por un admin."""

    def __init__(
        self,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee: GeoPoint,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        saved_by: UserId | None,
        saved_at: datetime,
    ) -> None:
        """Comprueba la forma; las distancias se miden solo al crearla (`create`)."""
        if not isinstance(golf_course_id, GolfCourseId):
            raise InvalidSavedHoleError(f"Invalid golf course id {golf_course_id!r}")
        if (
            not isinstance(hole_number, int)
            or isinstance(hole_number, bool)
            or not MIN_HOLE_NUMBER <= hole_number <= MAX_HOLE_NUMBER
        ):
            raise InvalidSavedHoleError(f"Hole number must be 1-18, got {hole_number!r}")
        if not isinstance(tee, GeoPoint) or not isinstance(green_center, GeoPoint):
            raise InvalidSavedHoleError("The tee and the green center must be GeoPoints")
        bends = tuple(bends)
        if not all(isinstance(bend, GeoPoint) for bend in bends):
            raise InvalidSavedHoleError("Bends must be GeoPoints")
        if len(bends) > MAX_BENDS:
            raise InvalidSavedHoleError(f"At most {MAX_BENDS} bends, got {len(bends)}")
        # None solo al leerla: si se borra la cuenta del admin, la línea se queda
        if saved_by is not None and not isinstance(saved_by, UserId):
            raise InvalidSavedHoleError("The admin who saves it must be a UserId")

        self._golf_course_id = golf_course_id
        self._hole_number = hole_number
        self._tee = tee
        self._bends = bends
        self._green_center = green_center
        self._saved_by = saved_by
        self._saved_at = saved_at

    @classmethod
    def create(
        cls,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee: GeoPoint,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        saved_by: UserId,
        course_location: GeoPoint | None,
    ) -> "SavedHole":
        """
        La línea que el admin guarda ahora.

        Raises:
            InvalidSavedHoleError: hoyo, puntos o codos mal formados, el green a
                menos de 40 o más de 750 m de la salida, o un punto a más de 3 km
                del campo
        """
        if not isinstance(saved_by, UserId):
            raise InvalidSavedHoleError("The admin who saves it must be a UserId")
        hole = cls(
            golf_course_id=golf_course_id,
            hole_number=hole_number,
            tee=tee,
            bends=bends,
            green_center=green_center,
            saved_by=saved_by,
            saved_at=datetime.now(UTC).replace(tzinfo=None),
        )
        problem = play_line_problem(tee, green_center, hole.play_line, course_location)
        if problem:
            raise InvalidSavedHoleError(problem)
        return hole

    @classmethod
    def reconstruct(
        cls,
        golf_course_id: GolfCourseId,
        hole_number: int,
        tee: GeoPoint,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        saved_by: UserId | None,
        saved_at: datetime,
    ) -> "SavedHole":
        """Leída de la BD: sin volver a medir, para que no deje de cargarse."""
        return cls(golf_course_id, hole_number, tee, bends, green_center, saved_by, saved_at)

    @property
    def golf_course_id(self) -> GolfCourseId:
        """El campo."""
        return self._golf_course_id

    @property
    def hole_number(self) -> int:
        """El hoyo, del 1 al 18."""
        return self._hole_number

    @property
    def tee(self) -> GeoPoint:
        """La salida de referencia."""
        return self._tee

    @property
    def bends(self) -> tuple[GeoPoint, ...]:
        """Los codos, como mucho dos."""
        return self._bends

    @property
    def green_center(self) -> GeoPoint:
        """El centro del green."""
        return self._green_center

    @property
    def saved_by(self) -> UserId | None:
        """El admin que la guardó (None si ya no existe su cuenta)."""
        return self._saved_by

    @property
    def saved_at(self) -> datetime:
        """Cuándo (UTC, sin zona)."""
        return self._saved_at

    @property
    def play_line(self) -> tuple[GeoPoint, ...]:
        """Salida, codos y green, en orden."""
        return (self._tee, *self._bends, self._green_center)
