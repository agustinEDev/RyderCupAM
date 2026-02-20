"""Excepciones compartidas de la capa de aplicación del módulo Competition."""


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


class InvalidTeeCategoryError(ValueError):
    """El valor de tee_category no es válido."""

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


class InvalidHoleNumberError(Exception):
    """El numero de hoyo no es valido."""

    pass
