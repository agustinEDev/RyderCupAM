"""
CourseHoleMap Aggregate Root - El mapa de los hoyos de un recorrido (BE #532).

Un recorrido tiene como mucho un mapa, identificado por el propio campo. Nace de
una importación de OpenStreetMap ya aprobado (Agustín, 17 oct: «si hay algo mal,
ya lo reportarán») y reimportar lo sustituye, esté como esté (18 oct). Lo que
corrige el admin va en la línea guardada del hoyo (`SavedHole`), aparte, y
prevalece sobre OSM.

Workflow:
    (importar) → APPROVED → (reimportar) → APPROVED
    Los pendientes de antes del 18 oct: PENDING_REVIEW → APPROVED | REJECTED, y
    reimportar los deja aprobados
"""

import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime

from src.modules.user.domain.value_objects.user_id import UserId

from ..value_objects.golf_course_id import GolfCourseId
from ..value_objects.hole_map_status import HoleMapStatus
from ..value_objects.mapped_hole import MappedHole

MAX_REJECTION_REASON_LENGTH = 500

# El contorno de un campo en OSM es una vía cerrada o una relación (multipolígono)
OSM_REFERENCE_PATTERN = re.compile(r"^(way|relation)/\d+$")


class HoleMapNotPendingError(ValueError):
    """Solo se revisa un mapa pendiente; este ya está aprobado o rechazado."""


class RejectionReasonTooLongError(ValueError):
    """El motivo de rechazo pasa del máximo."""


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _naive_utc(moment: datetime) -> datetime:
    """Las fechas del módulo van en UTC y sin zona (`timestamp without time zone`)."""
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


class CourseHoleMap:
    """
    Agregado raíz del mapa de un recorrido.

    Business Rules:
    - Al menos un hoyo, sin números repetidos; se admite un mapa parcial (los
      hoyos que faltan se tratan en el front como sin mapear).
    - La referencia OSM es `way/<id>` o `relation/<id>`.
    - Solo se revisa (aprobar o rechazar) un mapa pendiente.
    - Lo importado entra aprobado, sin nadie que lo revisara; reimportar sustituye
      los hoyos esté como esté el mapa, y lo deja aprobado y sin revisor.
    - El motivo de rechazo es opcional y de 500 caracteres como mucho.
    - La fecha de importación se guarda en UTC y sin zona, como el resto del módulo.
    """

    def __init__(
        self,
        golf_course_id: GolfCourseId,
        holes: Iterable[MappedHole],
        osm_reference: str,
        imported_at: datetime,
        status: HoleMapStatus,
        reviewed_by: UserId | None,
        reviewed_at: datetime | None,
        rejection_reason: str | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:
        """Constructor privado. Usar create()."""
        self._golf_course_id = golf_course_id
        self._holes = self._validated_holes(holes)
        self._osm_reference = self._validated_osm_reference(osm_reference)
        self._imported_at = _naive_utc(imported_at)
        self._status = status
        self._reviewed_by = reviewed_by
        self._reviewed_at = reviewed_at
        self._rejection_reason = rejection_reason
        self._created_at = created_at
        self._updated_at = updated_at

    @classmethod
    def create(
        cls,
        golf_course_id: GolfCourseId,
        holes: Iterable[MappedHole],
        osm_reference: str,
        imported_at: datetime,
    ) -> "CourseHoleMap":
        """Crea un mapa pendiente de revisión (el flujo de antes del 18 oct)."""
        return cls._new(
            golf_course_id, holes, osm_reference, imported_at, HoleMapStatus.PENDING_REVIEW
        )

    @classmethod
    def create_approved(
        cls,
        golf_course_id: GolfCourseId,
        holes: Iterable[MappedHole],
        osm_reference: str,
        imported_at: datetime,
    ) -> "CourseHoleMap":
        """
        Crea el mapa de una importación, ya aprobado y sin revisor: la fecha de
        la aprobación es la de la importación (la BD la exige a todo lo no pendiente).
        """
        hole_map = cls._new(
            golf_course_id, holes, osm_reference, imported_at, HoleMapStatus.APPROVED
        )
        hole_map._reviewed_at = hole_map._imported_at
        return hole_map

    @classmethod
    def _new(
        cls,
        golf_course_id: GolfCourseId,
        holes: Iterable[MappedHole],
        osm_reference: str,
        imported_at: datetime,
        status: HoleMapStatus,
    ) -> "CourseHoleMap":
        now = _now()
        return cls(
            golf_course_id=golf_course_id,
            holes=holes,
            osm_reference=osm_reference,
            imported_at=imported_at,
            status=status,
            reviewed_by=None,
            reviewed_at=None,
            rejection_reason=None,
            created_at=now,
            updated_at=now,
        )

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    @staticmethod
    def _validated_holes(holes: Iterable[MappedHole]) -> tuple[MappedHole, ...]:
        ordered = tuple(sorted(holes, key=lambda hole: hole.number))
        if not ordered:
            raise ValueError("A hole map needs at least one hole")
        repeated = sorted(n for n, count in Counter(h.number for h in ordered).items() if count > 1)
        if repeated:
            raise ValueError(f"A hole map cannot have duplicate hole numbers: {repeated}")
        return ordered

    @staticmethod
    def _validated_osm_reference(osm_reference: str) -> str:
        if not OSM_REFERENCE_PATTERN.match(osm_reference):
            raise ValueError(
                f"OSM reference must be 'way/<id>' or 'relation/<id>', got {osm_reference!r}"
            )
        return osm_reference

    def _ensure_pending(self) -> None:
        if self._status is not HoleMapStatus.PENDING_REVIEW:
            raise HoleMapNotPendingError(
                f"Only a pending hole map can be reviewed; this one is {self._status}"
            )

    # ------------------------------------------------------------------
    # Comportamiento
    # ------------------------------------------------------------------

    def approve(self, reviewer_id: UserId) -> None:
        """Un admin da el mapa por bueno: a partir de aquí lo ven los jugadores."""
        self._ensure_pending()
        now = _now()
        self._status = HoleMapStatus.APPROVED
        self._reviewed_by = reviewer_id
        self._reviewed_at = now
        self._updated_at = now

    def reject(self, reviewer_id: UserId, reason: str | None = None) -> None:
        """Un admin descarta el mapa, con un motivo opcional."""
        self._ensure_pending()
        cleaned = reason.strip() if reason else None
        if cleaned and len(cleaned) > MAX_REJECTION_REASON_LENGTH:
            raise RejectionReasonTooLongError(
                f"Rejection reason must be at most {MAX_REJECTION_REASON_LENGTH} characters"
            )
        now = _now()
        self._status = HoleMapStatus.REJECTED
        self._reviewed_by = reviewer_id
        self._reviewed_at = now
        self._rejection_reason = cleaned or None
        self._updated_at = now

    def reimport(
        self, holes: Iterable[MappedHole], osm_reference: str, imported_at: datetime
    ) -> None:
        """Sustituye lo importado, esté como esté el mapa, y lo deja aprobado sin revisor."""
        new_holes = self._validated_holes(holes)
        new_reference = self._validated_osm_reference(osm_reference)
        self._holes = new_holes
        self._osm_reference = new_reference
        self._imported_at = _naive_utc(imported_at)
        self._status = HoleMapStatus.APPROVED
        self._reviewed_by = None
        self._reviewed_at = self._imported_at
        self._rejection_reason = None
        self._updated_at = _now()

    def hole(self, number: int) -> MappedHole | None:
        """El hoyo con ese número, o None si el mapa no lo tiene."""
        return next((hole for hole in self._holes if hole.number == number), None)

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    @property
    def golf_course_id(self) -> GolfCourseId:
        return self._golf_course_id

    @property
    def holes(self) -> tuple[MappedHole, ...]:
        return self._holes

    @property
    def osm_reference(self) -> str:
        return self._osm_reference

    @property
    def imported_at(self) -> datetime:
        return self._imported_at

    @property
    def status(self) -> HoleMapStatus:
        return self._status

    @property
    def is_approved(self) -> bool:
        """Si está aprobado: solo entonces lo ven los jugadores."""
        return self._status is HoleMapStatus.APPROVED

    @property
    def reviewed_by(self) -> UserId | None:
        return self._reviewed_by

    @property
    def reviewed_at(self) -> datetime | None:
        return self._reviewed_at

    @property
    def rejection_reason(self) -> str | None:
        return self._rejection_reason

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at
