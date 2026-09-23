"""Excepciones compartidas de la capa de aplicación del módulo Competition."""

from datetime import datetime


class CompetitionNotFoundError(Exception):
    """La competición no existe."""

    pass


class RoundNotFoundError(Exception):
    """La ronda no existe."""

    pass


class NotCompetitionCreatorError(Exception):
    """El usuario no es el creador de la competición."""

    pass


class RoundNotModifiableError(Exception):
    """La ronda no puede modificarse en su estado actual."""

    pass


class CompetitionNotClosedError(Exception):
    """La competición no está en estado CLOSED."""

    pass


class MatchNotFoundError(Exception):
    """El partido no existe."""

    pass


class CompetitionNotDraftError(Exception):
    """La competición no está en estado DRAFT."""

    pass


class InsufficientPlayersError(Exception):
    """No hay suficientes jugadores aprobados."""

    pass


class InvalidTeeColorError(ValueError):
    """El valor de tee_color no es válido."""

    pass


class InvitationNotFoundError(Exception):
    """La invitacion no existe."""

    pass


class InviteeNotFoundError(Exception):
    """El invitee (user_id) no existe."""

    pass


class NotInviteeError(Exception):
    """El usuario no es el invitee de la invitacion."""

    pass


class NotMatchPlayerError(Exception):
    """El usuario no es un jugador del partido."""

    pass


class ScorecardNotReadyError(Exception):
    """La tarjeta no esta lista para ser entregada (hay hoyos sin validar)."""

    pass


class ScorecardAlreadySubmittedError(Exception):
    """El jugador ya entrego su tarjeta."""

    pass


class MatchNotScoringError(Exception):
    """El partido no esta en estado para registrar scores."""

    pass


class ScoringNotOpenYetError(Exception):
    """
    La anotacion de ese partido todavia no ha abierto (BE #305).

    Distinto de `MatchNotScoringError` a proposito: este rechazo lo arregla
    ESPERAR, asi que el movil tiene que conservar el golpe en su cola en vez de
    darlo por perdido. Lleva la hora de apertura para poder decirla.
    """

    error_code = "SCORING_NOT_OPEN_YET"

    def __init__(self, message: str, opens_at: datetime):
        super().__init__(message)
        self.opens_at = opens_at


class InvalidHoleNumberError(Exception):
    """El numero de hoyo no es valido."""

    pass


class HandicapEditNotAllowedError(Exception):
    """El hándicap personalizado no puede modificarse en el estado actual de la competición."""

    pass


class EnrollmentNotFoundError(Exception):
    """La inscripción no existe."""

    pass


class NotCreatorError(Exception):
    """El usuario no es el creador de la competición."""

    pass


class GolfCourseHasRoundsError(Exception):
    """El campo tiene rondas programadas, así que no se puede quitar.

    Antes no hacía falta: no se podían crear rondas hasta cerrar inscripciones,
    y para entonces los campos ya no se tocaban. Al poder corregir el montaje
    con las inscripciones abiertas (BE #323), las dos cosas conviven.
    """

    pass


class NotCompetitionParticipantError(Exception):
    """Quien pregunta no es de esta competicion.

    Sin esto, probando identificadores se leia la sesion de cualquiera, incluida
    la de una competicion privada (FE #655).
    """

    pass
