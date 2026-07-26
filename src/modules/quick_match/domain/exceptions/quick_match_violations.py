"""
QuickMatch-specific Business Rule Violations.

Type-safe exception subclasses para las reglas de negocio del modulo QuickMatch.
"""

from src.shared.domain.exceptions.business_rule_violation import BusinessRuleViolation


class InvalidQuickMatchStatusViolation(BusinessRuleViolation):
    """La transicion de estado solicitada no es valida para el estado actual."""

    pass


class QuickMatchFullViolation(BusinessRuleViolation):
    """La partida ya tiene el numero maximo de participantes para su formato."""

    pass


class DuplicateParticipantViolation(BusinessRuleViolation):
    """El usuario ya es participante de la partida."""

    pass


class NotQuickMatchParticipantViolation(BusinessRuleViolation):
    """El usuario no es participante de la partida."""

    pass


class InvalidTeamAssignmentViolation(BusinessRuleViolation):
    """El equipo indicado no es valido para el formato de la partida."""

    pass


class IncompleteRosterViolation(BusinessRuleViolation):
    """No se puede iniciar la partida sin el numero de jugadores requerido por el formato."""

    pass


class CreatorCannotBeRemovedViolation(BusinessRuleViolation):
    """El creador no puede ser eliminado como participante; debe cancelar la partida."""

    pass


class InvalidHoleScoreViolation(BusinessRuleViolation):
    """El score de hoyo indicado no es valido."""

    pass


class InvalidScorerConfigurationViolation(BusinessRuleViolation):
    """La configuracion de anotadores (scorer_ids) no es valida."""

    pass


class NotAssignedScorerViolation(BusinessRuleViolation):
    """El usuario no es el anotador asignado para registrar este score."""

    pass
