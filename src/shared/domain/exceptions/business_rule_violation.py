"""
Business Rule Violation - Excepción para violaciones de reglas de negocio.

Lanzada cuando una operación viola una regla de negocio del dominio
(ej: exceder límite de competiciones, enrollarse duplicado, etc.).

OWASP Coverage:
- A04: Insecure Design (business logic abuse prevention)
"""


class BusinessRuleViolation(Exception):
    """
    Excepción lanzada cuando se viola una regla de negocio.

    Diferencia con otras excepciones:
    - ValueError: Validación de formato/tipo
    - BusinessRuleViolation: Violación de reglas del dominio

    Example:
        >>> if competition_count >= MAX_COMPETITIONS_PER_USER:
        ...     raise BusinessRuleViolation(
        ...         "User cannot create more than 50 competitions"
        ...     )
    """

    pass
