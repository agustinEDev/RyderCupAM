"""
Competition-specific Business Rule Violations.

Type-safe exception subclasses para reemplazar string matching frágil.
Cada subclase representa una regla de negocio específica violada.

OWASP Coverage:
- A04: Insecure Design (business logic abuse prevention)

Example:
    >>> try:
    ...     CompetitionPolicy.can_enroll(...)
    ... except DuplicateEnrollmentViolation as e:
    ...     # Type-safe exception handling
    ...     raise AlreadyEnrolledError(str(e)) from e
"""

from src.shared.domain.exceptions.business_rule_violation import BusinessRuleViolation


class MaxCompetitionsExceededViolation(BusinessRuleViolation):
    """
    Lanzada cuando un usuario excede el límite de competiciones permitidas.

    Business Rule: Un usuario no puede crear más de MAX_COMPETITIONS_PER_CREATOR competiciones.

    Example:
        >>> raise MaxCompetitionsExceededViolation(
        ...     "User cannot create more than 50 competitions. Current count: 50."
        ... )
    """

    pass


class DuplicateEnrollmentViolation(BusinessRuleViolation):
    """
    Lanzada cuando un usuario intenta inscribirse en una competición donde ya está inscrito.

    Business Rule: Un usuario solo puede tener una inscripción activa por competición.

    Example:
        >>> raise DuplicateEnrollmentViolation(
        ...     "User user123 is already enrolled in competition comp456. "
        ...     "Existing enrollment: enroll789."
        ... )
    """

    pass


class MaxEnrollmentsExceededViolation(BusinessRuleViolation):
    """
    Lanzada cuando un usuario excede el límite de inscripciones activas permitidas.

    Business Rule: Un usuario no puede tener más de MAX_ENROLLMENTS_PER_USER inscripciones activas.

    Example:
        >>> raise MaxEnrollmentsExceededViolation(
        ...     "User cannot enroll in more than 20 competitions. Current enrollments: 20."
        ... )
    """

    pass


class InvalidCompetitionStatusViolation(BusinessRuleViolation):
    """
    Lanzada cuando se intenta realizar una acción en una competición con estado inválido.

    Business Rule: Ciertas operaciones solo están permitidas en estados específicos.
    Por ejemplo, enrollments solo se permiten en ACTIVE o CLOSED.

    Example:
        >>> raise InvalidCompetitionStatusViolation(
        ...     "Competition status is DRAFT. Enrollments only allowed in ACTIVE or CLOSED status."
        ... )
    """

    pass


class EnrollmentPastStartDateViolation(BusinessRuleViolation):
    """
    Lanzada cuando se intenta inscribir en una competición que ya ha comenzado.

    Business Rule: No se pueden aceptar inscripciones después de la fecha de inicio.

    Example:
        >>> raise EnrollmentPastStartDateViolation(
        ...     "Competition starts on 2026-06-01. Cannot enroll after start date."
        ... )
    """

    pass


class CompetitionFullViolation(BusinessRuleViolation):
    """
    Lanzada cuando una competición alcanza su capacidad máxima de jugadores.

    Business Rule: No se pueden inscribir más jugadores cuando se alcanza max_players.

    Example:
        >>> raise CompetitionFullViolation(
        ...     "Competition comp123 has reached maximum capacity (24 players). "
        ...     "Current enrollments: 24."
        ... )
    """

    pass


class InvalidDateRangeViolation(BusinessRuleViolation):
    """
    Lanzada cuando el rango de fechas de una competición es inválido.

    Business Rule: start_date debe ser anterior a end_date.

    Example:
        >>> raise InvalidDateRangeViolation(
        ...     "Competition 'Test': Start date (2026-06-05) must be before end date (2026-06-03)."
        ... )
    """

    pass


class MaxDurationExceededViolation(BusinessRuleViolation):
    """
    Lanzada cuando la duración de una competición excede el límite permitido.

    Business Rule: Una competición no puede durar más de MAX_COMPETITION_DURATION_DAYS días.

    Example:
        >>> raise MaxDurationExceededViolation(
        ...     "Competition 'Test': Duration (400 days) exceeds maximum allowed (365 days)."
        ... )
    """

    pass


# =============================================================================
# INVITATION VIOLATIONS
# =============================================================================


class DuplicateInvitationViolation(BusinessRuleViolation):
    """Lanzada cuando ya existe una invitacion PENDING para ese email+competition."""

    pass


class InvitationExpiredViolation(BusinessRuleViolation):
    """Lanzada cuando la invitacion ya ha expirado."""

    pass


class InvalidInvitationStatusViolation(BusinessRuleViolation):
    """Lanzada cuando el estado de la invitacion no permite la operacion."""

    pass


class InvitationCompetitionStatusViolation(BusinessRuleViolation):
    """Lanzada cuando el estado de la competicion no permite invitaciones."""

    pass


class SelfInvitationViolation(BusinessRuleViolation):
    """Lanzada cuando el creador intenta invitarse a si mismo."""

    pass


class AlreadyEnrolledInvitationViolation(BusinessRuleViolation):
    """Lanzada cuando el invitado ya esta inscrito en la competicion."""

    pass


class InvitationRateLimitViolation(BusinessRuleViolation):
    """Lanzada cuando se excede el limite de invitaciones por hora para una competicion."""

    pass
