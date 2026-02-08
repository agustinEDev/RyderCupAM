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


class InvalidTeeCategoryError(ValueError):
    """El valor de tee_category no es válido."""

    pass
