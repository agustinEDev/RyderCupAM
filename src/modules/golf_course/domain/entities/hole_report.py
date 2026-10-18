"""
HoleReport Entity - El reporte de un hoyo mal (entrega 7, Agustín, 18 oct 2026).

Un jugador ve que el hoyo del mapa está mal y lo reporta: un motivo y la línea
que propone (salida, hasta dos codos y centro del green). El hoyo vuelve a
«Pendientes» del admin; mientras, todos siguen viendo la línea de siempre.

Como una muestra, **no guarda quién lo mandó**, y de cuándo llegó solo el día
(UTC). El id lo genera el móvil, para que un reenvío cuente una vez. Por hoyo,
como mucho tres abiertos (MAX_REPORTS_PER_HOLE); guardar la línea del hoyo los
cierra todos, y el admin puede descartar uno.

La línea propuesta cumple la regla de cualquier línea de hoyo
(`play_line_problem`): de la salida al green entre 40 y 750 m en recta, y
ningún punto a más de 3 km del campo (si el campo tiene ubicación).
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID

from ..value_objects.geo_point import GeoPoint
from ..value_objects.golf_course_id import GolfCourseId
from ..value_objects.mapped_hole import MAX_HOLE_NUMBER, MIN_HOLE_NUMBER
from .hole_sample import MAX_BENDS, play_line_problem

MAX_REPORTS_PER_HOLE = 3


class HoleReportReason(StrEnum):
    """Por qué se reporta el hoyo: los tres motivos del menú «⋮»."""

    WRONG_HOLE = "WRONG_HOLE"  # «No es el hoyo correcto»
    WRONG_LINE = "WRONG_LINE"  # «La línea es incorrecta»
    HOLE_CHANGED = "HOLE_CHANGED"  # «El hoyo ha cambiado»


class InvalidHoleReportError(ValueError):
    """El reporte no vale: motivo, hoyo, puntos, codos o distancias."""


def _today() -> date:
    """El día de hoy en UTC: de la llegada no se guarda más."""
    return datetime.now(UTC).date()


class HoleReport:
    """
    El reporte de un hoyo: motivo y línea propuesta, sin autor y sin hora.

    Business Rules:
    - El id es un UUID (lo genera el móvil).
    - El motivo es un HoleReportReason.
    - Hoyo entero de 1 a 18.
    - La línea propuesta es entera: salida, hasta 2 codos y centro del green.
    - Al crearlo: el green a 40-750 m de la salida en recta y ningún punto a más
      de 3 km del campo (sin ubicación del campo, no se mira).
    """

    def __init__(
        self,
        id: UUID,
        golf_course_id: GolfCourseId,
        hole_number: int,
        reason: HoleReportReason,
        tee: GeoPoint,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        received_on: date,
    ) -> None:
        """Comprueba la forma; las distancias se miden solo al crearlo (`create`)."""
        if not isinstance(id, UUID):
            raise InvalidHoleReportError(f"Invalid report id {id!r}")
        if not isinstance(golf_course_id, GolfCourseId):
            raise InvalidHoleReportError(f"Invalid golf course id {golf_course_id!r}")
        # bool es un int en Python; un 3.0 o un True no son un número de hoyo
        if (
            not isinstance(hole_number, int)
            or isinstance(hole_number, bool)
            or not MIN_HOLE_NUMBER <= hole_number <= MAX_HOLE_NUMBER
        ):
            raise InvalidHoleReportError(f"Hole number must be 1-18, got {hole_number!r}")
        if not isinstance(reason, HoleReportReason):
            raise InvalidHoleReportError(f"Invalid report reason {reason!r}")
        # Un datetime también es un date: con él se colaría la hora
        if not isinstance(received_on, date) or isinstance(received_on, datetime):
            raise InvalidHoleReportError("The arrival must be a day, without time")
        if not isinstance(tee, GeoPoint):
            raise InvalidHoleReportError("A report proposes a whole line: the tee is required")
        if not isinstance(green_center, GeoPoint):
            raise InvalidHoleReportError("The green center must be a GeoPoint")
        bends = tuple(bends)
        if not all(isinstance(bend, GeoPoint) for bend in bends):
            raise InvalidHoleReportError("Bends must be GeoPoints")
        if len(bends) > MAX_BENDS:
            raise InvalidHoleReportError(f"At most {MAX_BENDS} bends, got {len(bends)}")

        self._id = id
        self._golf_course_id = golf_course_id
        self._hole_number = hole_number
        self._reason = reason
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
        reason: HoleReportReason,
        tee: GeoPoint,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        course_location: GeoPoint | None,
    ) -> "HoleReport":
        """
        Un reporte recién llegado, con el id que puso el móvil y el día de hoy.

        Raises:
            InvalidHoleReportError: motivo, hoyo, puntos o codos mal formados, el
                green a menos de 40 o más de 750 m de la salida, o un punto a más
                de 3 km del campo
        """
        report = cls(
            id=id,
            golf_course_id=golf_course_id,
            hole_number=hole_number,
            reason=reason,
            tee=tee,
            bends=bends,
            green_center=green_center,
            received_on=_today(),
        )
        problem = play_line_problem(
            report.tee, report.green_center, report.play_line, course_location
        )
        if problem:
            raise InvalidHoleReportError(problem)
        return report

    @classmethod
    def reconstruct(
        cls,
        id: UUID,
        golf_course_id: GolfCourseId,
        hole_number: int,
        reason: HoleReportReason,
        tee: GeoPoint,
        bends: Iterable[GeoPoint],
        green_center: GeoPoint,
        received_on: date,
    ) -> "HoleReport":
        """
        Un reporte leído de la BD: sin volver a medir distancias, para que uno
        que se guardó válido no deje de cargarse si mañana cambian los límites.
        """
        return cls(
            id=id,
            golf_course_id=golf_course_id,
            hole_number=hole_number,
            reason=reason,
            tee=tee,
            bends=bends,
            green_center=green_center,
            received_on=received_on,
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
    def reason(self) -> HoleReportReason:
        return self._reason

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
    def received_on(self) -> date:
        """El día (UTC) en que llegó; sin hora a propósito."""
        return self._received_on

    @property
    def play_line(self) -> tuple[GeoPoint, ...]:
        """Salida, codos y green, en orden."""
        return (self._tee, *self._bends, self._green_center)
