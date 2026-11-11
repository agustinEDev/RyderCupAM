"""
Field Limits - Constantes de límites de longitud para campos

Define límites estrictos para todos los campos de entrada del sistema
para prevenir ataques DoS con strings excesivamente largos y mejorar
la consistencia de validación.

OWASP Coverage:
- A04: Insecure Design (prevención de DoS con inputs largos)
- A03: Injection (límites ayudan a prevenir payloads largos)

Referencias:
- Email: RFC 5321 (límite 254 caracteres)
- Password: OWASP ASVS V2.1.1 (máximo 128)
- Nombres: Basado en estándares internacionales
"""


class FieldLimits:
    """
    Constantes de límites de longitud para validación de campos.

    Todas las constantes están documentadas con su justificación.
    """

    # ==================== USER FIELDS ====================

    # Email
    EMAIL_MAX_LENGTH = 254  # RFC 5321 (local@domain total)

    # Password
    PASSWORD_MAX_LENGTH = 128  # OWASP ASVS V2.1.1

    # Names (First Name, Last Name)
    NAME_MAX_LENGTH = 100  # Cubre nombres largos internacionales

    # Alias (apodo público, opcional)
    # El mínimo NO es cosmético: el autocompletado exige 2 caracteres para
    # disparar la búsqueda, así que un alias de uno solo sería inencontrable
    ALIAS_MIN_LENGTH = 2
    ALIAS_MAX_LENGTH = 20  # Cabe en una tarjeta de resultados sin truncarse

    # Full Name (para búsquedas)
    FULL_NAME_MAX_LENGTH = 200  # first + last + espacio
