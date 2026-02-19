"""
Competition Policy - Domain service con reglas de negocio para competiciones.

Centraliza las reglas de negocio para prevenir abuso de lógica de negocio
(ej: límites por usuario, duplicados, capacidad, restricciones temporales).

OWASP Coverage:
- A04: Insecure Design (business logic abuse prevention)
"""

from datetime import date, datetime

from src.modules.user.domain.value_objects.user_id import UserId

from ..exceptions.competition_violations import (
    CompetitionFullViolation,
    DuplicateEnrollmentViolation,
    EnrollmentPastStartDateViolation,
    InvalidCompetitionStatusViolation,
    InvalidDateRangeViolation,
    InvitationCompetitionStatusViolation,
    InvitationRateLimitViolation,
    MaxCompetitionsExceededViolation,
    MaxDurationExceededViolation,
    MaxEnrollmentsExceededViolation,
)
from ..value_objects.competition_id import CompetitionId
from ..value_objects.competition_status import CompetitionStatus

# Límites de recursos por usuario
MAX_COMPETITIONS_PER_CREATOR = 50
MAX_ENROLLMENTS_PER_USER = 20

# Límites de duración
MAX_COMPETITION_DURATION_DAYS = 365


class CompetitionPolicy:
    """
    Domain service con reglas de negocio para competiciones.

    Responsabilidades:
    - Validar límites de recursos por usuario
    - Prevenir duplicados
    - Validar capacidad y restricciones temporales
    - Centralizar business rules complejas

    Example:
        >>> policy = CompetitionPolicy()
        >>> policy.can_create_competition(user_id, existing_count=49)  # OK
        >>> policy.can_create_competition(user_id, existing_count=50)  # Raises
    """

    @staticmethod
    def can_create_competition(_creator_id: UserId, existing_count: int) -> None:
        """
        Valida si un usuario puede crear una nueva competición.

        Args:
            _creator_id: ID del usuario que quiere crear la competición (context only)
            existing_count: Número de competiciones activas del usuario

        Raises:
            MaxCompetitionsExceededViolation: Si excede el límite permitido

        Example:
            >>> CompetitionPolicy.can_create_competition(user_id, 49)  # OK
            >>> CompetitionPolicy.can_create_competition(user_id, 50)
            MaxCompetitionsExceededViolation: User cannot create more than 50 competitions
        """
        if existing_count >= MAX_COMPETITIONS_PER_CREATOR:
            raise MaxCompetitionsExceededViolation(
                f"User cannot create more than {MAX_COMPETITIONS_PER_CREATOR} "
                f"competitions. Current count: {existing_count}."
            )

    @staticmethod
    def can_enroll(
        user_id: UserId,
        competition_id: CompetitionId,
        existing_enrollment_id: str | None,
        competition_status: CompetitionStatus,
        competition_start_date: date,
        user_total_enrollments: int,
    ) -> None:
        """
        Valida si un usuario puede enrollarse en una competición.

        Args:
            user_id: ID del usuario
            competition_id: ID de la competición
            existing_enrollment_id: ID de enrollment existente (None si no existe)
            competition_status: Estado actual de la competición
            competition_start_date: Fecha de inicio de la competición
            user_total_enrollments: Total de enrollments activos del usuario

        Raises:
            DuplicateEnrollmentViolation: Si el usuario ya está inscrito
            MaxEnrollmentsExceededViolation: Si excede el límite de inscripciones
            InvalidCompetitionStatusViolation: Si el estado no permite enrollments
            EnrollmentPastStartDateViolation: Si intenta inscribirse después del inicio

        Example:
            >>> CompetitionPolicy.can_enroll(
            ...     user_id, comp_id, None, CompetitionStatus.ACTIVE,
            ...     date(2026, 6, 1), 5
            ... )  # OK
        """
        # 1. Prevenir duplicados
        if existing_enrollment_id is not None:
            raise DuplicateEnrollmentViolation(
                f"User {user_id} is already enrolled in competition {competition_id}. "
                f"Existing enrollment: {existing_enrollment_id}."
            )

        # 2. Validar límite de enrollments por usuario
        if user_total_enrollments >= MAX_ENROLLMENTS_PER_USER:
            raise MaxEnrollmentsExceededViolation(
                f"User cannot enroll in more than {MAX_ENROLLMENTS_PER_USER} "
                f"competitions. Current enrollments: {user_total_enrollments}."
            )

        # 3. Validar estado de la competición
        if competition_status not in [
            CompetitionStatus.ACTIVE,
            CompetitionStatus.CLOSED,
        ]:
            raise InvalidCompetitionStatusViolation(
                f"Competition status is {competition_status.value}. "
                "Enrollments only allowed in ACTIVE or CLOSED status."
            )

        # 4. Validar restricción temporal (competición no debe haber empezado)
        if datetime.now().date() >= competition_start_date:
            raise EnrollmentPastStartDateViolation(
                f"Competition starts on {competition_start_date}. Cannot enroll after start date."
            )

    @staticmethod
    def validate_capacity(
        current_enrollments: int, max_players: int, competition_id: CompetitionId
    ) -> None:
        """
        Valida que haya capacidad disponible en la competición.

        Args:
            current_enrollments: Número actual de enrollments aprobados
            max_players: Capacidad máxima de la competición
            competition_id: ID de la competición

        Raises:
            CompetitionFullViolation: Si la competición está llena

        Example:
            >>> CompetitionPolicy.validate_capacity(23, 24, comp_id)  # OK
            >>> CompetitionPolicy.validate_capacity(24, 24, comp_id)
            CompetitionFullViolation: Competition is full
        """
        if current_enrollments >= max_players:
            raise CompetitionFullViolation(
                f"Competition {competition_id} has reached maximum capacity "
                f"({max_players} players). Current enrollments: {current_enrollments}."
            )

    @staticmethod
    def can_send_invitation(competition_status: CompetitionStatus) -> None:
        """
        Valida si el estado de la competicion permite enviar invitaciones.

        Allowed: ACTIVE, CLOSED, IN_PROGRESS.

        Args:
            competition_status: Estado actual de la competicion

        Raises:
            InvitationCompetitionStatusViolation: Si el estado no permite invitaciones
        """
        allowed = {
            CompetitionStatus.ACTIVE,
            CompetitionStatus.CLOSED,
            CompetitionStatus.IN_PROGRESS,
        }
        if competition_status not in allowed:
            raise InvitationCompetitionStatusViolation(
                f"Competition status is {competition_status.value}. "
                "Invitations only allowed in ACTIVE, CLOSED, or IN_PROGRESS status."
            )

    @staticmethod
    def can_accept_invitation(competition_status: CompetitionStatus) -> None:
        """
        Valida si el estado de la competicion permite aceptar invitaciones.

        Allowed: ACTIVE, CLOSED, IN_PROGRESS.

        Args:
            competition_status: Estado actual de la competicion

        Raises:
            InvitationCompetitionStatusViolation: Si el estado no permite aceptar
        """
        allowed = {
            CompetitionStatus.ACTIVE,
            CompetitionStatus.CLOSED,
            CompetitionStatus.IN_PROGRESS,
        }
        if competition_status not in allowed:
            raise InvitationCompetitionStatusViolation(
                f"Competition status is {competition_status.value}. "
                "Accepting invitations only allowed in ACTIVE, CLOSED, or IN_PROGRESS status."
            )

    @staticmethod
    def validate_invitation_rate(
        recent_invitations: int, max_players: int, competition_id: CompetitionId
    ) -> None:
        """
        Valida que no se excedan las invitaciones por hora para una competicion.

        El limite es max_players por hora: no tiene sentido enviar mas invitaciones
        que participantes maximos en una hora.

        Args:
            recent_invitations: Invitaciones enviadas en la ultima hora
            max_players: Capacidad maxima de la competicion
            competition_id: ID de la competicion

        Raises:
            InvitationRateLimitViolation: Si se excede el limite
        """
        if recent_invitations >= max_players:
            raise InvitationRateLimitViolation(
                f"Competition {competition_id}: Too many invitations sent in the last hour "
                f"({recent_invitations}/{max_players}). "
                f"Limit is {max_players} invitations per hour."
            )

    @staticmethod
    def validate_date_range(start_date: date, end_date: date, competition_name: str) -> None:
        """
        Valida que el rango de fechas sea razonable.

        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            competition_name: Nombre de la competición (para mensaje de error)

        Raises:
            InvalidDateRangeViolation: Si start_date >= end_date
            MaxDurationExceededViolation: Si la duración excede el máximo permitido

        Note:
            No valida que la fecha sea futura (eso es responsabilidad de la capa de aplicación).
            Aquí solo validamos invariantes de negocio: orden y duración razonable.

        Example:
            >>> CompetitionPolicy.validate_date_range(
            ...     date(2026, 6, 1), date(2026, 6, 3), "Test"
            ... )  # OK
        """
        # 1. Validar orden lógico
        if start_date >= end_date:
            raise InvalidDateRangeViolation(
                f"Competition '{competition_name}': Start date ({start_date}) "
                f"must be before end date ({end_date})."
            )

        # 2. Validar duración razonable
        duration_days = (end_date - start_date).days
        if duration_days > MAX_COMPETITION_DURATION_DAYS:
            raise MaxDurationExceededViolation(
                f"Competition '{competition_name}': Duration ({duration_days} days) "
                f"exceeds maximum allowed ({MAX_COMPETITION_DURATION_DAYS} days)."
            )
