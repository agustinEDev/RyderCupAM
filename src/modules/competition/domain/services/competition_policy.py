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

# Freno anti-abuso de invitaciones: correos que una competición puede disparar en
# una hora. Es un límite de seguridad, no un número de producto, y por eso deja de
# seguir al cupo (`max_players`): el día que el cupo suba, seguirlo convertiría una
# competición en un emisor de tantos correos por hora como jugadores admita.
#
# Con el cupo de hoy (100) esto no cambia nada: 100 es el techo que ya había de
# hecho, y el límite efectivo `min(max_players, MAX_INVITATIONS_PER_HOUR)` deja una
# competición de 12 frenando en 12, como siempre. Está puesto para que subir el
# cupo no arrastre el freno sin que nadie lo decida.
MAX_INVITATIONS_PER_HOUR = 100


# Cerrada la inscripcion ya no quedan plazas: ni se invita ni se acepta (#710)
INSCRIPCION_CERRADA = frozenset({CompetitionStatus.CLOSED, CompetitionStatus.IN_PROGRESS})
SIN_PLAZAS = "No quedan plazas en esta competición: la inscripción está cerrada"


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
            EnrollmentPastStartDateViolation: Si intenta inscribirse pasado el día de inicio

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

        # 4. Validar restricción temporal: hasta el día de inicio INCLUIDO (BE #372).
        # El día del torneo es cuando más gente se apunta; lo que protege el
        # torneo es el estado (en juego ya no) y la aprobación del organizador
        if datetime.now().date() > competition_start_date:
            raise EnrollmentPastStartDateViolation(
                f"Competition started on {competition_start_date}. Cannot enroll after start date."
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

        Allowed: DRAFT, ACTIVE.

        CLOSED e IN_PROGRESS no desde el 24 sep (#710): cerrada la inscripcion
        no quedan plazas, y una invitacion enviada ahi nadie podria aceptarla.

        DRAFT entra desde BE #319: invitar a la primera persona ES abrir el
        torneo, y quien invita no tiene por que pasar antes por un boton cuyo
        unico trabajo es mover un estado. La apertura la hace el caso de uso
        con `invitation_opens_enrollment`.

        Args:
            competition_status: Estado actual de la competicion

        Raises:
            InvitationCompetitionStatusViolation: Si el estado no permite invitaciones
        """
        if competition_status in INSCRIPCION_CERRADA:
            raise InvitationCompetitionStatusViolation(SIN_PLAZAS)
        allowed = {
            CompetitionStatus.DRAFT,
            CompetitionStatus.ACTIVE,
        }
        if competition_status not in allowed:
            raise InvitationCompetitionStatusViolation(
                f"Competition status is {competition_status.value}. "
                "Invitations only allowed in DRAFT or ACTIVE status."
            )

    @staticmethod
    def invitation_opens_enrollment(competition_status: CompetitionStatus) -> bool:
        """
        Indica si enviar una invitacion debe abrir las inscripciones.

        Invitar a la primera persona ES abrir el torneo, asi que lo abre
        (BE #319).

        Desde BE #332 la unica que sigue en DRAFT es la que espera su apertura
        programada, asi que esto ya solo alcanza a esas: invitar a alguien es
        adelantar esa apertura a proposito. Al abrirse, la competicion deja de
        anunciar los dias —lo hace `activate()`—, porque si no la ficha seguiria
        prometiendo una apertura futura de algo que acaba de abrirse.

        Args:
            competition_status: Estado actual de la competicion

        Returns:
            True si esta invitacion tiene que abrir las inscripciones
        """
        return competition_status == CompetitionStatus.DRAFT

    @staticmethod
    def can_accept_invitation(competition_status: CompetitionStatus) -> None:
        """
        Valida si el estado de la competicion permite aceptar invitaciones.

        Allowed: ACTIVE.

        Cerrada o en juego, no (decidido el 24 sep, #710): con los equipos
        hechos, entrar descuadraba los partidos.

        Args:
            competition_status: Estado actual de la competicion

        Raises:
            InvitationCompetitionStatusViolation: Si el estado no permite aceptar
        """
        if competition_status in INSCRIPCION_CERRADA:
            raise InvitationCompetitionStatusViolation(SIN_PLAZAS)
        if competition_status != CompetitionStatus.ACTIVE:
            raise InvitationCompetitionStatusViolation(
                f"Competition status is {competition_status.value}. "
                "Accepting invitations only allowed in ACTIVE status."
            )

    @staticmethod
    def validate_invitation_rate(
        recent_invitations: int, max_players: int, competition_id: CompetitionId
    ) -> None:
        """
        Valida que no se excedan las invitaciones por hora para una competicion.

        El limite es `min(max_players, MAX_INVITATIONS_PER_HOUR)`: no tiene sentido
        enviar mas invitaciones que participantes maximos, y por encima de
        MAX_INVITATIONS_PER_HOUR manda el freno anti-abuso, que no sigue al cupo.

        Args:
            recent_invitations: Invitaciones enviadas en la ultima hora
            max_players: Capacidad maxima de la competicion
            competition_id: ID de la competicion

        Raises:
            InvitationRateLimitViolation: Si se excede el limite
        """
        limite = min(max_players, MAX_INVITATIONS_PER_HOUR)
        if recent_invitations >= limite:
            raise InvitationRateLimitViolation(
                f"Competition {competition_id}: Too many invitations sent in the last hour "
                f"({recent_invitations}/{limite}). "
                f"Limit is {limite} invitations per hour."
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
        if start_date > end_date:
            raise InvalidDateRangeViolation(
                f"Competition '{competition_name}': Start date ({start_date}) "
                f"must be before or equal to end date ({end_date})."
            )

        # 2. Validar duración razonable
        duration_days = (end_date - start_date).days
        if duration_days > MAX_COMPETITION_DURATION_DAYS:
            raise MaxDurationExceededViolation(
                f"Competition '{competition_name}': Duration ({duration_days} days) "
                f"exceeds maximum allowed ({MAX_COMPETITION_DURATION_DAYS} days)."
            )
