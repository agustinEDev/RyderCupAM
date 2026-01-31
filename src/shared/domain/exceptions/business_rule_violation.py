"""
Business Rule Violation - Excepción para violaciones de reglas de negocio.

Lanzada cuando una operación viola una regla de negocio del dominio
(ej: exceder límite de competiciones, enrollarse duplicado, etc.).

OWASP Coverage:
- A04: Insecure Design (business logic abuse prevention)
"""


class BusinessRuleViolation(Exception):  # noqa: N818
    """
    Excepción lanzada cuando se viola una regla de negocio.

    Note:
        El nombre NO termina en "Error" intencionalmente (convención DDD).
        Las violaciones de reglas de negocio son eventos del dominio, no errores técnicos.

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
