"""
Social-specific Business Rule Violations.

Type-safe exception subclasses para las reglas de negocio del modulo Social (Friendship).

OWASP Coverage:
- A04: Insecure Design (business logic abuse prevention)
"""

from src.shared.domain.exceptions.business_rule_violation import BusinessRuleViolation


class SelfFriendRequestViolation(BusinessRuleViolation):
    """Un usuario no puede enviarse una solicitud de amistad a si mismo."""

    pass


class DuplicateFriendRequestViolation(BusinessRuleViolation):
    """Ya existe una relacion de amistad (pendiente o aceptada) entre ambos usuarios."""

    pass


class InvalidFriendshipStatusViolation(BusinessRuleViolation):
    """La transicion de estado solicitada no es valida para el estado actual."""

    pass


class FriendshipRateLimitViolation(BusinessRuleViolation):
    """Se ha excedido el limite de solicitudes de amistad enviadas."""

    pass


class BlockedUserViolation(BusinessRuleViolation):
    """La accion no es posible porque existe un bloqueo entre ambos usuarios."""

    pass


class DuplicateFriendshipViolation(BusinessRuleViolation):
    """Ya existe una relacion (de cualquier estado) para esta pareja de usuarios.

    Traduce la violacion del indice unico `uq_friendship_pair` (o su equivalente
    en el repositorio en memoria) a una excepcion de dominio, para que la capa
    de aplicacion no dependa de la jerarquia de excepciones de SQLAlchemy.
    """

    pass
