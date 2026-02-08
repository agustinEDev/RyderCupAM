"""
GolfCourse Aggregate Root - Campo de golf con workflow de aprobación.

Workflow: PENDING_APPROVAL → APPROVED/REJECTED (inmutable después)
Ver ADR-032 para detalles del workflow de aprobación.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import reconstructor

from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent
from src.shared.domain.value_objects.country_code import CountryCode

from ..events.golf_course_approved_event import GolfCourseApprovedEvent
from ..events.golf_course_rejected_event import GolfCourseRejectedEvent
from ..events.golf_course_requested_event import GolfCourseRequestedEvent
from ..value_objects.approval_status import ApprovalStatus
from ..value_objects.course_type import CourseType
from ..value_objects.golf_course_id import GolfCourseId
from .hole import Hole
from .tee import Tee


class GolfCourse:
    """
    Agregado raíz para campos de golf.

    Responsabilidades:
    - Gestionar información del campo (nombre, país, tipo)
    - Gestionar tees (2-6 salidas con ratings WHS)
    - Gestionar hoyos (18 hoyos con par y stroke index)
    - Workflow de aprobación Admin

    Business Rules:
    - Exactamente 18 hoyos
    - Stroke indices únicos (1-18)
    - Par total entre 66 y 76
    - 2-10 tees (5 categorías x 2 géneros max)
    - Unique (category, gender) combinations
    - No mezclar gendered/non-gendered tees de la misma categoría
    - Estados inmutables: APPROVED/REJECTED

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

        # Validar invariantes
        self._validate_holes()
        self._validate_tees()

    @reconstructor
    def _init_on_load(self) -> None:
        """
        SQLAlchemy reconstructor - called after entity is loaded from database.

        Ensures _domain_events is initialized when SQLAlchemy hydrates the entity.
        """
        if not hasattr(self, "_domain_events"):
            self._domain_events: list[DomainEvent] = []

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
                category=tee.category,
                gender=tee.gender,
                identifier=tee.identifier,
                course_rating=tee.course_rating,
                slope_rating=tee.slope_rating,
            )
            self._tees.append(new_tee)

        del self._holes[:]  # Elimina todos los elementos in-place
        from src.modules.golf_course.domain.entities.hole import Hole as HoleEntity

        for hole in holes:
            new_hole = HoleEntity(
                number=hole.number,
                par=hole.par,
                stroke_index=hole.stroke_index,
            )
            self._holes.append(new_hole)

        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

        # Validar invariantes
        self._validate_holes()
        self._validate_tees()

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
            # Crear nuevo Tee con los mismos datos
            from src.modules.golf_course.domain.entities.tee import Tee

            new_tee = Tee(
                category=tee.category,
                gender=tee.gender,
                identifier=tee.identifier,
                course_rating=tee.course_rating,
                slope_rating=tee.slope_rating,
            )
            self._tees.append(new_tee)

        del self._holes[:]  # Elimina todos los elementos in-place
        for hole in clone._holes:
            # Crear nuevo Hole con los mismos datos
            from src.modules.golf_course.domain.entities.hole import Hole

            new_hole = Hole(
                number=hole.number,
                par=hole.par,
                stroke_index=hole.stroke_index,
            )
            self._holes.append(new_hole)

        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

        # Quitar marca de pending update
        self._is_pending_update = False

        # Validar invariantes
        self._validate_holes()
        self._validate_tees()

    def _validate_holes(self) -> None:
        """
        Valida que haya exactamente 18 hoyos con índices únicos y par válido.

        Raises:
            ValueError: Si la validación falla
        """
        # Debe tener exactamente 18 hoyos
        if len(self._holes) != 18:  # noqa: PLR2004
            raise ValueError(f"Golf course must have exactly 18 holes, got {len(self._holes)}")

        # Stroke indices deben ser únicos (1-18)
        stroke_indices = [h.stroke_index for h in self._holes]
        if len(stroke_indices) != len(set(stroke_indices)):
            raise ValueError("Stroke indices must be unique (1-18)")

        expected_indices = set(range(1, 19))
        actual_indices = set(stroke_indices)
        if expected_indices != actual_indices:
            raise ValueError(f"Stroke indices must be exactly 1-18, got {sorted(actual_indices)}")

        # Par total debe estar entre 66 y 76
        total_par = sum(h.par for h in self._holes)
        if not (66 <= total_par <= 76):  # noqa: PLR2004
            raise ValueError(f"Total par must be between 66 and 76, got {total_par}")

    def _validate_tees(self) -> None:
        """
        Valida tees: cantidad 2-10, unicidad (category, gender), consistencia gendered.

        Raises:
            ValueError: Si la validación falla
        """
        if not (2 <= len(self._tees) <= 10):  # noqa: PLR2004
            raise ValueError(
                f"Golf course must have between 2 and 10 tees, got {len(self._tees)}"
            )

        # Unicidad: combinación (category, gender) debe ser única
        seen_combos: set[tuple[str, str | None]] = set()
        for tee in self._tees:
            gender_val = tee.gender.value if tee.gender else None
            combo = (tee.category.value, gender_val)
            if combo in seen_combos:
                raise ValueError(
                    f"Duplicate tee combination: ({tee.category.value}, "
                    f"{gender_val or 'None'})"
                )
            seen_combos.add(combo)

        # Consistencia: para una misma categoría, no mezclar gendered y non-gendered
        from collections import defaultdict

        gender_by_category: dict[str, set[str | None]] = defaultdict(set)
        for tee in self._tees:
            gender_val = tee.gender.value if tee.gender else None
            gender_by_category[tee.category.value].add(gender_val)

        for cat, genders in gender_by_category.items():
            if None in genders and len(genders) > 1:
                raise ValueError(
                    f"Category '{cat}' cannot mix gendered and non-gendered tees"
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
        return self._holes.copy()

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
        """Retorna el par total del campo."""
        return sum(h.par for h in self._holes)

    @property
    def original_golf_course_id(self) -> GolfCourseId | None:
        """Retorna el ID del campo original si este es un clone/update proposal."""
        return self._original_golf_course_id

    @property
    def is_pending_update(self) -> bool:
        """Retorna TRUE si este campo tiene un clone pendiente de aprobación."""
        return self._is_pending_update
