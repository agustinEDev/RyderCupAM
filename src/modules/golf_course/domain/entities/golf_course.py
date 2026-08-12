"""
GolfCourse Aggregate Root - Campo de golf con workflow de aprobación.

Workflow: PENDING_APPROVAL → APPROVED/REJECTED (inmutable después)
Ver ADR-032 para detalles del workflow de aprobación.
"""

from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime

from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

from ..events.golf_course_approved_event import GolfCourseApprovedEvent
from ..events.golf_course_rejected_event import GolfCourseRejectedEvent
from ..events.golf_course_requested_event import GolfCourseRequestedEvent
from ..value_objects.approval_status import ApprovalStatus
from ..value_objects.course_type import CourseType
from ..value_objects.golf_course_id import GolfCourseId
from ..value_objects.tee_color import TeeColor
from .hole import Hole
from .tee import Tee

HOLES_PER_ROUND = 18

# Un campo federado puede tener desde una sola salida hasta catorce (el Old
# Course de Atalaya tiene doce, y hay un recorrido con catorce).
MIN_TEES = 1
MAX_TEES = 14

# Rangos por tipo de campo. Los estándar mantienen el rigor de WHS; los cortos
# usan márgenes más amplios porque el sistema no los valora en la misma escala.
PAR_RANGE_BY_COURSE_TYPE: dict[CourseType, tuple[int, int]] = {
    CourseType.STANDARD_18: (66, 76),
    CourseType.EXECUTIVE: (61, 65),
    CourseType.PITCH_AND_PUTT: (54, 60),
}

# El techo de slope de los campos estándar se sube a 160 pese a que WHS define
# 155 como máximo: hay campos federados publicados por encima (el Villa de
# Madrid, negras de mujeres, está en 157) y rechazarlos por un redondeo ajeno
# sería perder campos reales. El suelo sí se mantiene estricto, porque es lo
# que permite detectar erratas de origen.
SLOPE_RANGE_BY_COURSE_TYPE: dict[CourseType, tuple[int, int]] = {
    CourseType.STANDARD_18: (55, 160),
    CourseType.EXECUTIVE: (40, 155),
    CourseType.PITCH_AND_PUTT: (40, 155),
}

RATING_RANGE_BY_COURSE_TYPE: dict[CourseType, tuple[float, float]] = {
    CourseType.STANDARD_18: (50.0, 90.0),
    CourseType.EXECUTIVE: (45.0, 90.0),
    CourseType.PITCH_AND_PUTT: (45.0, 90.0),
}


class GolfCourse:
    """
    Agregado raíz para campos de golf.

    Responsabilidades:
    - Gestionar información del campo (nombre, país, tipo)
    - Gestionar salidas (1-14, cada una con sus ratings WHS y su tarjeta)
    - Workflow de aprobación Admin

    Business Rules:
    - Cada salida tiene sus 18 hoyos, con par, stroke index y distancia propios
    - Números de hoyo y stroke indices 1-18 sin repetir
    - Par total, slope y course rating dentro del rango de su tipo de campo
    - 1-14 salidas, únicas por color (o por identificador si el color es OTHER)
    - No mezclar salidas con y sin género para un mismo color
    - Estados inmutables: APPROVED/REJECTED

    La tarjeta del campo (`holes`) es derivada: no se persiste, se toma de la
    primera salida. Existe para los consumidores que no necesitan el detalle
    por barra.

    Example:
        >>> course = GolfCourse.create(
        ...     name="Real Club de Golf El Prat",
        ...     country_code=CountryCode("ES"),
        ...     course_type=CourseType.STANDARD_18,
        ...     creator_id=UserId.generate(),
        ...     tees=[...],
        ...     holes=[...]
        ... )
        >>> course.approve()  # Admin
        >>> course.reject(reason="Datos incorrectos")  # Admin
    """

    def __init__(
        self,
        id: GolfCourseId,
        name: str,
        country_code: CountryCode,
        course_type: CourseType,
        creator_id: UserId,
        tees: list[Tee],
        holes: list[Hole],
        approval_status: ApprovalStatus,
        rejection_reason: str | None,
        created_at: datetime,
        updated_at: datetime,
        original_golf_course_id: GolfCourseId | None = None,
        is_pending_update: bool = False,
        domain_events: list[DomainEvent] | None = None,
    ) -> None:
        """
        Constructor privado. Usar create() o reconstruct().

        Args:
            id: Identificador único del campo
            name: Nombre del campo
            country_code: Código ISO del país
            course_type: Tipo de campo
            creator_id: Usuario que solicitó el campo
            tees: Lista de salidas (2-6)
            holes: Lista de hoyos (18)
            approval_status: Estado de aprobación
            rejection_reason: Razón de rechazo (solo si REJECTED)
            created_at: Fecha de creación
            updated_at: Fecha de última actualización
            original_golf_course_id: Si no es None, este es un clone/update proposal del original
            is_pending_update: TRUE si este campo tiene un clone pendiente de aprobación
            domain_events: Eventos de dominio (opcional)
        """
        self._id = id
        self._name = name
        self._country_code = country_code
        self._course_type = course_type
        self._creator_id = creator_id
        self._tees = list(tees)  # Defensive copy
        self._holes = list(holes)  # Defensive copy
        self._approval_status = approval_status
        self._rejection_reason = rejection_reason
        self._created_at = created_at
        self._updated_at = updated_at
        self._original_golf_course_id = original_golf_course_id
        self._is_pending_update = is_pending_update
        self._domain_events: list[DomainEvent] = domain_events or []

        # Reconciliar la tarjeta del campo con la de cada salida antes de validar
        self._sync_holes_and_tees()

        # Validar invariantes
        self._validate_holes()
        self._validate_tees()

    def _sync_holes_and_tees(self) -> None:
        """
        Reconcilia la tarjeta de referencia del campo con la de cada salida.

        Un campo puede describirse de dos maneras, y ambas siguen siendo válidas:

        - Con una sola tarjeta para todo el campo (como se creaba hasta ahora):
          esos hoyos se copian a las salidas que no traigan tarjeta propia.
        - Con una tarjeta por salida (lo que publica la RFEG): en ese caso la
          tarjeta de referencia del campo se toma de la primera salida.

        Así los consumidores que solo leen `golf_course.holes` siguen
        funcionando, y quien necesite la distancia o el índice exactos de una
        barra concreta los pide a su Tee.
        """
        if not getattr(self, "_holes", None):
            for tee in self._tees:
                if tee.holes:
                    self._holes = [replace(hole) for hole in tee.holes]
                    break

        for tee in self._tees:
            if not tee.holes and self._holes:
                tee.holes = [replace(hole) for hole in self._holes]

    @classmethod
    def create(
        cls,
        name: str,
        country_code: CountryCode,
        course_type: CourseType,
        creator_id: UserId,
        tees: list[Tee],
        holes: list[Hole],
    ) -> "GolfCourse":
        """
        Factory method para crear un nuevo campo de golf.

        El campo se crea en estado PENDING_APPROVAL.

        Args:
            name: Nombre del campo (3-200 caracteres)
            country_code: Código ISO del país
            course_type: Tipo de campo
            creator_id: Usuario que solicita el campo
            tees: Lista de salidas (2-6)
            holes: Lista de hoyos (18)

        Returns:
            GolfCourse: Campo creado en estado PENDING_APPROVAL

        Raises:
            ValueError: Si los datos no son válidos
        """
        # Validar nombre
        if not (3 <= len(name) <= 200):  # noqa: PLR2004
            raise ValueError("Course name must be between 3 and 200 characters")

        now = datetime.now(UTC).replace(tzinfo=None)
        golf_course_id = GolfCourseId.generate()

        golf_course = cls(
            id=golf_course_id,
            name=name,
            country_code=country_code,
            course_type=course_type,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
            approval_status=ApprovalStatus.PENDING_APPROVAL,
            rejection_reason=None,
            created_at=now,
            updated_at=now,
        )

        # Registrar evento de creación
        golf_course._record_event(
            GolfCourseRequestedEvent(
                golf_course_id=str(golf_course_id),
                golf_course_name=name,
                creator_id=str(creator_id),
            )
        )

        return golf_course

    @classmethod
    def reconstruct(
        cls,
        id: GolfCourseId,
        name: str,
        country_code: CountryCode,
        course_type: CourseType,
        creator_id: UserId,
        tees: list[Tee],
        holes: list[Hole],
        approval_status: ApprovalStatus,
        rejection_reason: str | None,
        created_at: datetime,
        updated_at: datetime,
        original_golf_course_id: GolfCourseId | None = None,
        is_pending_update: bool = False,
    ) -> "GolfCourse":
        """
        Reconstruye un GolfCourse desde persistencia.

        Usado por el repositorio para hidratar objetos desde BD.
        """
        return cls(
            id=id,
            name=name,
            country_code=country_code,
            course_type=course_type,
            creator_id=creator_id,
            tees=tees,
            holes=holes,
            approval_status=approval_status,
            rejection_reason=rejection_reason,
            created_at=created_at,
            updated_at=updated_at,
            original_golf_course_id=original_golf_course_id,
            is_pending_update=is_pending_update,
        )

    def approve(self) -> None:
        """
        Aprueba el campo de golf (Admin).

        El campo queda disponible para todos los Creators.

        Raises:
            ValueError: Si el estado actual no permite aprobación
        """
        if self._approval_status != ApprovalStatus.PENDING_APPROVAL:
            raise ValueError(
                f"Cannot approve course in status {self._approval_status}. "
                "Only PENDING_APPROVAL can be approved."
            )

        self._approval_status = ApprovalStatus.APPROVED
        self._rejection_reason = None
        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

        # Registrar evento de aprobación
        self._record_event(
            GolfCourseApprovedEvent(
                golf_course_id=str(self._id),
                golf_course_name=self._name,
                creator_id=str(self._creator_id),
            )
        )

    def reject(self, reason: str) -> None:
        """
        Rechaza el campo de golf (Admin).

        El campo queda visible solo para Admin y Creator (owner).

        Args:
            reason: Razón del rechazo (10-500 caracteres)

        Raises:
            ValueError: Si el estado actual no permite rechazo o razón inválida
        """
        if self._approval_status != ApprovalStatus.PENDING_APPROVAL:
            raise ValueError(
                f"Cannot reject course in status {self._approval_status}. "
                "Only PENDING_APPROVAL can be rejected."
            )

        if not (10 <= len(reason) <= 500):  # noqa: PLR2004
            raise ValueError("Rejection reason must be between 10 and 500 characters")

        self._approval_status = ApprovalStatus.REJECTED
        self._rejection_reason = reason
        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

        # Registrar evento de rechazo
        self._record_event(
            GolfCourseRejectedEvent(
                golf_course_id=str(self._id),
                golf_course_name=self._name,
                creator_id=str(self._creator_id),
                rejection_reason=reason,
            )
        )

    def update(
        self,
        name: str,
        country_code: CountryCode,
        course_type: CourseType,
        tees: list[Tee],
        holes: list[Hole],
    ) -> None:
        """
        Actualiza los campos del golf course.

        Este método actualiza todos los campos modificables in-place.
        IMPORTANTE: La lógica de negocio (si crear clone o actualizar directo)
        debe estar en el use case, no aquí.

        Args:
            name: Nuevo nombre del campo
            country_code: Nuevo código de país
            course_type: Nuevo tipo de campo
            tees: Nueva lista de tees
            holes: Nueva lista de hoyos

        Raises:
            ValueError: Si los datos no son válidos
        """
        # Validar nombre
        if not (3 <= len(name) <= 200):  # noqa: PLR2004
            raise ValueError("Course name must be between 3 and 200 characters")

        # Actualizar campos
        self._name = name
        self._country_code = country_code
        self._course_type = course_type

        # Actualizar colecciones rastreadas por SQLAlchemy
        # IMPORTANTE: Creamos NUEVOS objetos en lugar de usar los pasados como parámetro
        # para evitar conflictos de IDs y golf_course_id con SQLAlchemy
        del self._tees[:]  # Elimina todos los elementos in-place
        from src.modules.golf_course.domain.entities.tee import Tee as TeeEntity

        for tee in tees:
            new_tee = TeeEntity(
                gender=tee.gender,
                color=tee.color,
                identifier=tee.identifier,
                course_rating=tee.course_rating,
                slope_rating=tee.slope_rating,
                holes=[replace(hole) for hole in tee.holes],
            )
            self._tees.append(new_tee)

        del self._holes[:]  # Elimina todos los elementos in-place
        for hole in holes:
            self._holes.append(replace(hole))

        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

        # Reconciliar tarjetas antes de validar: si las salidas llegan sin la
        # suya, heredan la del campo
        self._sync_holes_and_tees()

        # Validar invariantes
        self._validate_holes()
        self._validate_tees()

    def apply_update(
        self,
        name: str,
        country_code: CountryCode,
        course_type: CourseType,
        tees: list[Tee],
        holes: list[Hole],
        is_admin: bool,
    ) -> "GolfCourse | None":
        """
        Aplica una actualización al campo de golf según las reglas de negocio.

        Reglas:
        - REJECTED → error (no editable)
        - Admin → siempre in-place (retorna None)
        - Creator + PENDING → in-place (retorna None)
        - Creator + APPROVED → crea clone (retorna el clone)

        Args:
            name: Nuevo nombre
            country_code: Nuevo código de país
            course_type: Nuevo tipo de campo
            tees: Nueva lista de tees
            holes: Nueva lista de hoyos
            is_admin: Si el usuario es Admin

        Returns:
            None si se actualizó in-place, GolfCourse clone si se creó propuesta

        Raises:
            ValueError: Si el campo está REJECTED
        """
        if self._approval_status == ApprovalStatus.REJECTED:
            raise ValueError(
                "Cannot edit a REJECTED golf course. Please create a new request instead."
            )

        # Admin o PENDING_APPROVAL → actualización in-place
        if is_admin or self._approval_status == ApprovalStatus.PENDING_APPROVAL:
            self.update(
                name=name,
                country_code=country_code,
                course_type=course_type,
                tees=tees,
                holes=holes,
            )
            return None

        # Creator + APPROVED → crear clone como update proposal
        clone = GolfCourse.create(
            name=name,
            country_code=country_code,
            course_type=course_type,
            creator_id=self._creator_id,
            tees=tees,
            holes=holes,
        )

        # Reconstruir clone con campos especiales (link al original, status PENDING)
        clone_proposal = GolfCourse.reconstruct(
            id=clone.id,
            name=clone.name,
            country_code=clone.country_code,
            course_type=clone.course_type,
            creator_id=clone.creator_id,
            tees=clone.tees,
            holes=clone.holes,
            approval_status=ApprovalStatus.PENDING_APPROVAL,
            rejection_reason=None,
            created_at=clone.created_at,
            updated_at=clone.updated_at,
            original_golf_course_id=self._id,
            is_pending_update=False,
        )

        # Marcar original como "tiene cambios pendientes"
        self.mark_as_pending_update()

        return clone_proposal

    def mark_as_pending_update(self) -> None:
        """
        Marca este campo como 'tiene cambios pendientes de aprobación'.

        Usado cuando un creator edita un campo APPROVED y se crea un clone.
        """
        self._is_pending_update = True
        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

    def clear_pending_update(self) -> None:
        """
        Quita la marca de 'cambios pendientes'.

        Usado cuando el admin aprueba o rechaza el clone.
        """
        self._is_pending_update = False
        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

    def apply_changes_from_clone(self, clone: "GolfCourse") -> None:
        """
        Aplica todos los cambios de un clone a este campo original.

        Usado cuando el admin aprueba un update y necesitamos copiar
        todos los campos del clone al original.

        Args:
            clone: El clone con los cambios propuestos

        Raises:
            ValueError: Si el clone no es realmente un clone de este campo
        """
        if clone.original_golf_course_id != self._id:
            raise ValueError(f"Clone {clone.id} is not a clone of this golf course {self._id}")

        # Copiar todos los campos modificables del clone
        self._name = clone._name
        self._country_code = clone._country_code
        self._course_type = clone._course_type

        # Actualizar colecciones rastreadas por SQLAlchemy
        # IMPORTANTE: Creamos NUEVOS objetos en lugar de copiar referencias
        # porque los objetos del clone ya tienen golf_course_id asignado
        del self._tees[:]  # Elimina todos los elementos in-place
        for tee in clone._tees:
            # Crear nuevo Tee con los mismos datos, incluida su tarjeta
            new_tee = Tee(
                gender=tee.gender,
                color=tee.color,
                identifier=tee.identifier,
                course_rating=tee.course_rating,
                slope_rating=tee.slope_rating,
                holes=[replace(hole) for hole in tee.holes],
            )
            self._tees.append(new_tee)

        del self._holes[:]  # Elimina todos los elementos in-place
        for hole in clone.holes:
            self._holes.append(replace(hole))

        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

        # Quitar marca de pending update
        self._is_pending_update = False

        # Reconciliar tarjetas antes de validar
        self._sync_holes_and_tees()

        # Validar invariantes
        self._validate_holes()
        self._validate_tees()

    def _validate_holes(self) -> None:
        """
        Valida la tarjeta de referencia: 18 hoyos, índices únicos y par en rango.

        El rango de par depende del tipo de campo, y se comprueba sobre la
        tarjeta de referencia y no sobre cada salida: hay recorridos federados
        donde el par varía entre barras (un hoyo que es par 5 desde las de
        atrás y par 4 desde las de delante), y exigir el mismo rango a todas
        dejaría fuera campos perfectamente válidos.

        Raises:
            ValueError: Si la validación falla
        """
        reference_card = self.holes
        if len(reference_card) != HOLES_PER_ROUND:
            raise ValueError(
                f"Golf course must have exactly {HOLES_PER_ROUND} holes, got {len(reference_card)}"
            )

        # Los números de hoyo también deben ser 1-18 sin repetir. La tarjeta de
        # referencia se copia a las salidas asignando la lista, lo que no pasa
        # por el validador de Tee, así que si no se comprueba aquí una tarjeta
        # con hoyos repetidos acabaría propagándose a todas las salidas.
        hole_numbers = sorted(h.number for h in reference_card)
        if hole_numbers != list(range(1, HOLES_PER_ROUND + 1)):
            raise ValueError(
                f"Hole numbers must be exactly 1-{HOLES_PER_ROUND} without "
                f"duplicates, got {hole_numbers}"
            )

        stroke_indices = sorted(h.stroke_index for h in reference_card)
        if stroke_indices != list(range(1, HOLES_PER_ROUND + 1)):
            raise ValueError(
                f"Stroke indices must be exactly 1-{HOLES_PER_ROUND} without "
                f"duplicates, got {stroke_indices}"
            )

        min_par, max_par = PAR_RANGE_BY_COURSE_TYPE[self._course_type]
        total_par = sum(h.par for h in reference_card)
        if not (min_par <= total_par <= max_par):
            raise ValueError(
                f"Total par for a {self._course_type} course must be between "
                f"{min_par} and {max_par}, got {total_par}"
            )

    def _validate_tees(self) -> None:
        """
        Valida las salidas: cantidad, unicidad por color y género, y ratings.

        La unicidad va por (color, género) y no por (categoría, género): con
        campos de hasta catorce salidas, varias comparten categoría — un campo
        no basta con el nombre que le demos: lo que identifica físicamente una
        salida es su color.

        Raises:
            ValueError: Si la validación falla
        """
        if not (MIN_TEES <= len(self._tees) <= MAX_TEES):
            raise ValueError(
                f"Golf course must have between {MIN_TEES} and {MAX_TEES} tees, "
                f"got {len(self._tees)}"
            )

        seen_combos: set[tuple[str, str | None]] = set()
        for tee in self._tees:
            combo = tee.unique_key
            if combo in seen_combos:
                raise ValueError(f"Duplicate tee: {tee.display_name} ({combo[1] or 'no gender'})")
            seen_combos.add(combo)

        # Consistencia: para una misma salida, no mezclar con y sin género
        genders_by_tee: dict[str, set[str | None]] = defaultdict(set)
        for tee in self._tees:
            genders_by_tee[tee.unique_key[0]].add(tee.gender.value if tee.gender else None)

        for tee_key, genders in genders_by_tee.items():
            if None in genders and len(genders) > 1:
                raise ValueError(f"Tee '{tee_key}' cannot mix gendered and non-gendered tees")

        self._validate_tee_ratings()

    def _validate_tee_ratings(self) -> None:
        """
        Comprueba que los ratings WHS caen en el rango propio del tipo de campo.

        Los campos estándar mantienen el rigor de WHS. Los cortos (pitch & putt
        y ejecutivos) usan márgenes más amplios porque el sistema no los valora
        en la misma escala: hay pitch & putt federados con slope por debajo de
        55 y course rating por debajo de 50.
        """
        min_slope, max_slope = SLOPE_RANGE_BY_COURSE_TYPE[self._course_type]
        min_rating, max_rating = RATING_RANGE_BY_COURSE_TYPE[self._course_type]

        for tee in self._tees:
            if not (min_slope <= tee.slope_rating <= max_slope):
                raise ValueError(
                    f"Slope rating for a {self._course_type} course must be between "
                    f"{min_slope} and {max_slope}, got {tee.slope_rating} "
                    f"on tee {tee.display_name}"
                )
            if not (min_rating <= tee.course_rating <= max_rating):
                raise ValueError(
                    f"Course rating for a {self._course_type} course must be between "
                    f"{min_rating} and {max_rating}, got {tee.course_rating} "
                    f"on tee {tee.display_name}"
                )

    # Domain Events Management

    def _record_event(self, event: DomainEvent) -> None:
        """Registra un evento de dominio."""
        self._domain_events.append(event)

    def pull_domain_events(self) -> list[DomainEvent]:
        """
        Retorna y limpia los eventos de dominio.

        Returns:
            Lista de eventos de dominio
        """
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events

    def clear_domain_events(self) -> None:
        """Limpia los eventos de dominio sin retornarlos."""
        self._domain_events.clear()

    # Properties

    @property
    def id(self) -> GolfCourseId:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def country_code(self) -> CountryCode:
        return self._country_code

    @property
    def course_type(self) -> CourseType:
        return self._course_type

    @property
    def creator_id(self) -> UserId:
        return self._creator_id

    @property
    def tees(self) -> list[Tee]:
        return self._tees.copy()

    @property
    def holes(self) -> list[Hole]:
        """
        Tarjeta de referencia del campo.

        No se persiste: la tarjeta real vive en cada salida, y esta se deriva
        de la primera que tenga una. Se calcula al consultarla y no al cargar
        el agregado porque durante el evento de carga de SQLAlchemy las
        relaciones eager todavía no están garantizadas.
        """
        own_holes = getattr(self, "_holes", None)
        if own_holes:
            return sorted(own_holes, key=lambda h: h.number)

        for tee in self._tees:
            if tee.holes:
                return sorted((replace(hole) for hole in tee.holes), key=lambda h: h.number)

        return []

    @property
    def approval_status(self) -> ApprovalStatus:
        return self._approval_status

    @property
    def rejection_reason(self) -> str | None:
        return self._rejection_reason

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def total_par(self) -> int:
        """Retorna el par total del campo, según su tarjeta de referencia."""
        return sum(h.par for h in self.holes)

    @property
    def original_golf_course_id(self) -> GolfCourseId | None:
        """Retorna el ID del campo original si este es un clone/update proposal."""
        return self._original_golf_course_id

    @property
    def is_pending_update(self) -> bool:
        """Retorna TRUE si este campo tiene un clone pendiente de aprobación."""
        return self._is_pending_update

    # Metodos de consulta

    def has_tee(self, color: TeeColor, gender: Gender | None, identifier: str | None = None) -> bool:
        """
        Retorna True si el campo tiene esa salida.

        Una salida se identifica por color y género. Cuando el color es OTHER
        hace falta además el identificador, porque OTHER puede repetirse en un
        mismo campo (las "Championship" británicas y las combinadas
        estadounidenses caen ahí).
        """
        return any(
            tee.color == color
            and tee.gender == gender
            and (color is not TeeColor.OTHER or tee.identifier == identifier)
            for tee in self._tees
        )

    def find_tee(
        self, color: TeeColor, gender: Gender | None, identifier: str | None = None
    ) -> Tee | None:
        """Devuelve la salida que corresponde a ese color y género, si existe."""
        for tee in self._tees:
            if (
                tee.color == color
                and tee.gender == gender
                and (color is not TeeColor.OTHER or tee.identifier == identifier)
            ):
                return tee
        return None
