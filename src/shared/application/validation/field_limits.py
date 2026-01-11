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
- Password: OWASP ASVS V2.1.1 (mínimo 12, máximo 128)
- Nombres: Basado en estándares internacionales
"""


class FieldLimits:
    """
    Constantes de límites de longitud para validación de campos.

    Todas las constantes están documentadas con su justificación.
    """

    # ==================== USER FIELDS ====================

    # Email
    EMAIL_MIN_LENGTH = 5  # "a@b.c" es el email más corto válido
    EMAIL_MAX_LENGTH = 254  # RFC 5321 (local@domain total)

    # Password
    PASSWORD_MIN_LENGTH = 12  # OWASP ASVS V2.1.1 (2024)
    PASSWORD_MAX_LENGTH = 128  # OWASP ASVS V2.1.1

    # Names (First Name, Last Name)
    NAME_MIN_LENGTH = 2  # "Li" es un nombre válido corto
    NAME_MAX_LENGTH = 100  # Cubre nombres largos internacionales

    # Full Name (para búsquedas)
    FULL_NAME_MIN_LENGTH = 3  # "A B" mínimo
    FULL_NAME_MAX_LENGTH = 200  # first + last + espacio

    # Country Code
    COUNTRY_CODE_LENGTH = 2  # ISO 3166-1 alpha-2 (fijo)

    # ==================== COMPETITION FIELDS ====================

    # Competition Name
    COMPETITION_NAME_MIN_LENGTH = 3  # "ABC" mínimo
    COMPETITION_NAME_MAX_LENGTH = 200  # Nombres descriptivos largos

    # Competition Description (si se añade en futuro)
    DESCRIPTION_MAX_LENGTH = 2000  # Texto descriptivo

    # Team Names
    TEAM_NAME_MIN_LENGTH = 2  # "AB" mínimo
    TEAM_NAME_MAX_LENGTH = 100  # Nombres de equipos

    # ==================== TOKENS ====================

    # Verification Token
    VERIFICATION_TOKEN_MIN_LENGTH = 32  # UUID sin guiones (32 hex chars)
    VERIFICATION_TOKEN_MAX_LENGTH = 256  # Tokens JWT largos

    # JWT Token
    JWT_TOKEN_MIN_LENGTH = 20  # JWT mínimo teórico
    JWT_TOKEN_MAX_LENGTH = 2048  # JWT con muchos claims

    # ==================== GENERIC STRINGS ====================

    # Generic Text Field (mensajes, comentarios)
    TEXT_FIELD_MAX_LENGTH = 5000

    # Generic Short String (nombres, títulos)
    SHORT_STRING_MAX_LENGTH = 255

    # ==================== NUMERIC FIELDS ====================

    # Handicap
    HANDICAP_MIN_VALUE = -10.0  # WHS permite hasta -10
    HANDICAP_MAX_VALUE = 54.0  # WHS límite superior

    # Max Players (competitions)
    MAX_PLAYERS_MIN = 2  # Mínimo para competición
    MAX_PLAYERS_MAX = 200  # Límite razonable

    # Handicap Percentage
    HANDICAP_PERCENTAGE_MIN = 0  # 0% (sin ajuste)
    HANDICAP_PERCENTAGE_MAX = 100  # 100% (hándicap completo)

    @classmethod
    def get_all_limits(cls) -> dict:
        """
        Retorna diccionario con todos los límites definidos.

        Útil para documentación y testing.

        Returns:
            dict: Diccionario con nombre_constante: valor
        """
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and key.isupper()
        }

    @classmethod
    def validate_limit(
        cls, field_name: str, value: str | None, min_length: int, max_length: int
    ) -> None:
        """
        Valida que un campo cumple con los límites de longitud.

        Args:
            field_name: Nombre del campo (para mensajes de error)
            value: Valor a validar
            min_length: Longitud mínima permitida
            max_length: Longitud máxima permitida

        Raises:
            ValueError: Si el valor no cumple los límites

        Example:
            >>> FieldLimits.validate_limit("first_name", "John", 2, 100)
            # OK, no lanza excepción
            >>> FieldLimits.validate_limit("first_name", "J", 2, 100)
            # ValueError: first_name debe tener entre 2 y 100 caracteres
        """
        if value is None:
            return

        length = len(value)

        if length < min_length:
            raise ValueError(
                f"{field_name} debe tener al menos {min_length} caracteres. "
                f"Recibido: {length} caracteres."
            )

        if length > max_length:
            raise ValueError(
                f"{field_name} no puede exceder {max_length} caracteres. "
                f"Recibido: {length} caracteres."
            )
