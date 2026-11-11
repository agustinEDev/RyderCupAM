"""
Custom Validators - Validadores personalizados para Pydantic

Proporciona validadores estrictos que van más allá de las validaciones
básicas de Pydantic, implementando best practices de seguridad.

OWASP Coverage:
- A03: Injection (validación estricta de formatos)
"""

import re
from typing import ClassVar

from src.shared.application.validation.field_limits import FieldLimits


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
                f"{field_name} solo puede contener letras, números, espacios y los signos . _ -"
            )

        # Un alias de solo signos —"...", "-_-"— no identifica a nadie y no
        # se puede buscar por él
        if not any(c.isalnum() for c in normalized):
            raise ValueError(f"{field_name} debe contener al menos una letra o un número")

        return normalized
