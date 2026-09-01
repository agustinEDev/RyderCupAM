"""
Custom Validators - Validadores personalizados para Pydantic

Proporciona validadores estrictos que van más allá de las validaciones
básicas de Pydantic, implementando best practices de seguridad.

OWASP Coverage:
- A03: Injection (validación estricta de formatos)
- A07: Authentication Failures (validación de email robusta)
"""

import re
from typing import Any, ClassVar

from src.shared.application.validation.field_limits import FieldLimits


class EmailValidator:
    """
    Validador estricto de email según RFC 5322 (simplificado).

    Más estricto que EmailStr de Pydantic, rechaza casos edge
    que técnicamente son válidos pero raramente usados.

    Referencias:
    - RFC 5322 (Internet Message Format)
    - OWASP Input Validation Cheat Sheet
    """

    # Regex estricto para email (simplificado de RFC 5322)
    # Permite: letras, números, ., -, _ en local part
    # Permite: letras, números, -, . en domain
    # Requiere: al menos un . en domain
    EMAIL_REGEX = re.compile(
        r"^[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}"  # Local part (max 64 chars)
        r"@"
        r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}"  # Domain (max 253 chars)
        r"\.[a-zA-Z]{2,}$"  # TLD (mínimo 2 chars)
    )

    # Lista negra de dominios temporales/desechables (opcional)
    # Descomentada por defecto, pero disponible para uso futuro
    DISPOSABLE_EMAIL_DOMAINS: ClassVar[list[str]] = [
        # "tempmail.com",
        # "guerrillamail.com",
        # "10minutemail.com",
        # "mailinator.com",
    ]

    @classmethod
    def validate(cls, email: str) -> str:
        """
        Valida que un email cumpla con formato estricto.

        Args:
            email: Email a validar

        Returns:
            Email normalizado (lowercase, trimmed)

        Raises:
            ValueError: Si el email no es válido

        Examples:
            >>> EmailValidator.validate("user@example.com")
            "user@example.com"

            >>> EmailValidator.validate("  USER@EXAMPLE.COM  ")
            "user@example.com"

            >>> EmailValidator.validate("invalid@")
            # ValueError: Formato de email inválido

            >>> EmailValidator.validate("user@domain")
            # ValueError: Email debe contener un dominio válido con TLD
        """
        if not email:
            raise ValueError("Email no puede estar vacío")

        # Normalizar email a lowercase y eliminar espacios
        normalized = email.strip().lower()

        # Validar longitud total (RFC 5321)
        if len(normalized) > 254:  # noqa: PLR2004
            raise ValueError("Email no puede exceder 254 caracteres")

        if len(normalized) < 5:  # noqa: PLR2004
            raise ValueError("Email debe tener al menos 5 caracteres")

        # Validar que contenga @
        if "@" not in normalized:
            raise ValueError("Formato de email inválido. Use el formato: usuario@dominio.com")

        # Validar partes del email (ANTES del regex para mensajes específicos)
        local, domain = normalized.rsplit("@", 1)

        # Local part no puede exceder 64 caracteres (RFC 5321)
        if len(local) > 64:  # noqa: PLR2004
            raise ValueError("La parte local del email (antes de @) no puede exceder 64 caracteres")

        # Domain no puede exceder 253 caracteres (RFC 5321)
        if len(domain) > 253:  # noqa: PLR2004
            raise ValueError("El dominio del email (después de @) no puede exceder 253 caracteres")

        # Validar formato con regex (después de validaciones específicas)
        if not cls.EMAIL_REGEX.match(normalized):
            raise ValueError("Formato de email inválido. Use el formato: usuario@dominio.com")

        # Domain debe tener al menos un punto
        if "." not in domain:
            raise ValueError("Email debe contener un dominio válido con TLD (ej: .com, .es)")

        # Validación opcional: rechazar dominios desechables
        if cls.DISPOSABLE_EMAIL_DOMAINS and domain in cls.DISPOSABLE_EMAIL_DOMAINS:
            raise ValueError("No se permiten emails de dominios temporales")

        return normalized

    @classmethod
    def is_valid(cls, email: str) -> bool:
        """
        Verifica si un email es válido sin lanzar excepción.

        Args:
            email: Email a verificar

        Returns:
            True si es válido, False en caso contrario

        Example:
            >>> EmailValidator.is_valid("user@example.com")
            True

            >>> EmailValidator.is_valid("invalid")
            False
        """
        try:
            cls.validate(email)
            return True
        except ValueError:
            return False


def validate_email_strict(email: str | Any) -> str:
    """
    Función helper para usar EmailValidator en Pydantic field_validator.

    Args:
        email: Email a validar (puede ser Any por Pydantic)

    Returns:
        Email validado y normalizado

    Raises:
        ValueError: Si el email no es válido

    Example:
        >>> from pydantic import BaseModel, field_validator
        >>> class UserDTO(BaseModel):
        ...     email: str
        ...
        ...     @field_validator('email')
        ...     @classmethod
        ...     def validate_email(cls, v):
        ...         return validate_email_strict(v)
    """
    if not isinstance(email, str):
        raise ValueError(f"Email debe ser un string, recibido: {type(email).__name__}")

    return EmailValidator.validate(email)


class NameValidator:
    """
    Validador para nombres de personas.

    Reglas:
    - Solo letras, espacios, guiones y apóstrofes
    - No números ni caracteres especiales
    - Mínimo 2 caracteres, máximo 100
    """

    # Permite letras (incluyendo acentos), espacios, guiones y apóstrofes
    # Ejemplos válidos: "María", "Jean-Pierre", "O'Connor", "José María"
    NAME_REGEX = re.compile(r"^[a-zA-ZÀ-ÿ' -]+$")

    @classmethod
    def validate(cls, name: str, field_name: str = "name") -> str:
        """
        Valida que un nombre cumpla con las reglas.

        Args:
            name: Nombre a validar
            field_name: Nombre del campo (para mensajes de error)

        Returns:
            Nombre validado y normalizado

        Raises:
            ValueError: Si el nombre no es válido

        Examples:
            >>> NameValidator.validate("John")
            "John"

            >>> NameValidator.validate("María José")
            "María José"

            >>> NameValidator.validate("John123")
            # ValueError: name solo puede contener letras...
        """
        if not name:
            raise ValueError(f"{field_name} no puede estar vacío")

        # Trim
        normalized = name.strip()

        # Validar longitud
        if len(normalized) < 2:  # noqa: PLR2004
            raise ValueError(f"{field_name} debe tener al menos 2 caracteres")

        if len(normalized) > 100:  # noqa: PLR2004
            raise ValueError(f"{field_name} no puede exceder 100 caracteres")

        # Validar formato
        if not cls.NAME_REGEX.match(normalized):
            raise ValueError(
                f"{field_name} solo puede contener letras, espacios, guiones y apóstrofes. "
                f"No se permiten números ni caracteres especiales."
            )

        # Validar que no sea solo espacios/guiones
        if not any(c.isalpha() for c in normalized):
            raise ValueError(f"{field_name} debe contener al menos una letra")

        return normalized


class AliasValidator:
    """
    Validador del alias público del usuario.

    El alias sustituye al nombre real en toda la aplicación, así que es lo
    que otra gente teclea para encontrarte. De ahí las reglas:

    - 2 a 20 caracteres.
    - Letras (con acentos), dígitos, espacio y `.`, `_`, `-`.
    - Ni emoji ni HTML.
    - Se guarda tal y como se escribe; la unicidad la decide la base de
      datos ignorando mayúsculas.
    """

    # NO se usa el rango `À-ÿ` de NameValidator: incluye los signos de
    # multiplicar (U+00D7) y dividir (U+00F7), que no son letras. Aquí se
    # saltan los dos a propósito en vez de heredar el fallo
    ALIAS_REGEX = re.compile(r"^[a-zA-Z0-9À-ÖØ-öø-ÿ._\- ]+$")

    # Los límites viven en FieldLimits, que es de donde los leen también los
    # DTO: dos copias del número acabarían discrepando
    MIN_LENGTH: ClassVar[int] = FieldLimits.ALIAS_MIN_LENGTH
    MAX_LENGTH: ClassVar[int] = FieldLimits.ALIAS_MAX_LENGTH

    @classmethod
    def validate(cls, alias: str, field_name: str = "alias") -> str:
        """
        Valida y normaliza un alias.

        Args:
            alias: Alias a validar
            field_name: Nombre del campo (para mensajes de error)

        Returns:
            Alias normalizado: sin espacios en los bordes y sin espacios
            internos repetidos

        Raises:
            ValueError: Si el alias no cumple las reglas

        Examples:
            >>> AliasValidator.validate("Chuchi")
            "Chuchi"

            >>> AliasValidator.validate("  Chu  chi  ")
            "Chu chi"

            >>> AliasValidator.validate("C")
            # ValueError: alias debe tener al menos 2 caracteres
        """
        if not alias:
            raise ValueError(f"{field_name} no puede estar vacío")

        # Normalizar: bordes fuera y espacios internos repetidos a uno solo.
        # Sin esto, "Chu  chi" y "Chu chi" serían aliases distintos y el
        # índice único no los vería como el mismo
        normalized = " ".join(alias.split())

        if len(normalized) < cls.MIN_LENGTH:
            raise ValueError(f"{field_name} debe tener al menos {cls.MIN_LENGTH} caracteres")

        if len(normalized) > cls.MAX_LENGTH:
            raise ValueError(f"{field_name} no puede exceder {cls.MAX_LENGTH} caracteres")

        if not cls.ALIAS_REGEX.match(normalized):
            raise ValueError(
                f"{field_name} solo puede contener letras, números, espacios y los signos "
                f". _ -"
            )

        # Un alias de solo signos —"...", "-_-"— no identifica a nadie y no
        # se puede buscar por él
        if not any(c.isalnum() for c in normalized):
            raise ValueError(f"{field_name} debe contener al menos una letra o un número")

        return normalized


def validate_country_code(code: str | None) -> str | None:
    """
    Valida código de país ISO 3166-1 alpha-2.

    Args:
        code: Código de país (2 letras mayúsculas)

    Returns:
        Código normalizado (uppercase) o None

    Raises:
        ValueError: Si el formato no es válido

    Examples:
        >>> validate_country_code("ES")
        "ES"

        >>> validate_country_code("es")
        "ES"

        >>> validate_country_code("ESP")
        # ValueError: Código de país debe tener exactamente 2 letras
    """
    if code is None:
        return None

    # Normalizar
    normalized = code.strip().upper()

    # Validar longitud
    if len(normalized) != 2:  # noqa: PLR2004
        raise ValueError("Código de país debe tener exactamente 2 letras (ISO 3166-1 alpha-2)")

    # Validar que solo contenga letras
    if not normalized.isalpha():
        raise ValueError("Código de país solo puede contener letras (A-Z)")

    return normalized


def validate_no_script_tags(text: str) -> str:
    """
    Valida que un texto NO contenga tags de script.

    Esta es una validación adicional de seguridad que rechaza
    inputs con patrones sospechosos.

    Args:
        text: Texto a validar

    Returns:
        Texto original si es válido

    Raises:
        ValueError: Si contiene tags de script

    Examples:
        >>> validate_no_script_tags("Hello world")
        "Hello world"

        >>> validate_no_script_tags("<script>alert(1)</script>")
        # ValueError: Input contiene contenido no permitido
    """
    if not text:
        return text

    # Patrones peligrosos (case-insensitive)
    dangerous_patterns = [
        r"<script",
        r"javascript:",
        r"onerror=",
        r"onclick=",
        r"onload=",
        r"eval\(",
        r"expression\(",
    ]

    text_lower = text.lower()

    for pattern in dangerous_patterns:
        if re.search(pattern, text_lower):
            raise ValueError(
                "Input contiene contenido no permitido. "
                "Por favor, elimine tags HTML y código JavaScript."
            )

    return text
