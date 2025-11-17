# -*- coding: utf-8 -*-
"""
CountryCode Value Object - Código ISO 3166-1 alpha-2 de país.

Este Value Object representa un código de país estandarizado de 2 letras.
Usado para referenciar países de forma consistente en toda la aplicación.
"""

from dataclasses import dataclass


class InvalidCountryCodeError(Exception):
    """Excepción lanzada cuando un código de país no es válido."""
    pass


@dataclass(frozen=True)
class CountryCode:
    """
    Value Object para códigos ISO de país.

    Inmutable y validado automáticamente.
    Representa un código de país según ISO 3166-1 alpha-2.

    Reglas de negocio:
    - Debe tener exactamente 2 caracteres
    - Solo puede contener letras (A-Z)
    - Se normaliza a mayúsculas automáticamente

    Ejemplos:
        >>> code1 = CountryCode("ES")
        >>> print(code1.value)
        'ES'

        >>> code2 = CountryCode("es")  # Se normaliza
        >>> print(code2.value)
        'ES'

        >>> code3 = CountryCode("pt")
        >>> code3 == CountryCode("PT")
        True

        >>> CountryCode("E")  # Lanza InvalidCountryCodeError (muy corto)
        >>> CountryCode("ESP")  # Lanza InvalidCountryCodeError (muy largo)
        >>> CountryCode("E1")  # Lanza InvalidCountryCodeError (contiene número)
    """

    value: str

    def __post_init__(self):
        """
        Validación y normalización automática del código de país.

        Normaliza a mayúsculas y valida formato ISO 3166-1 alpha-2.
        """
        if not isinstance(self.value, str):
            raise InvalidCountryCodeError(
                f"El código debe ser un string, se recibió {type(self.value).__name__}"
            )

        # 1. Normalizar: quitar espacios y convertir a mayúsculas
        normalized = self.value.strip().upper()

        # 2. Validar longitud (exactamente 2 caracteres)
        if len(normalized) != 2:
            raise InvalidCountryCodeError(
                f"El código de país debe tener exactamente 2 caracteres. "
                f"Se recibió: '{self.value}' (longitud: {len(normalized)})"
            )

        # 3. Validar que solo contenga letras
        if not normalized.isalpha():
            raise InvalidCountryCodeError(
                f"El código de país solo puede contener letras (A-Z). "
                f"Se recibió: '{self.value}'"
            )

        # 4. Asignar valor normalizado (usar object.__setattr__ porque es frozen)
        object.__setattr__(self, 'value', normalized)

    def __str__(self) -> str:
        """Representación string legible."""
        return self.value

    def __eq__(self, other) -> bool:
        """
        Operador de igualdad - Comparación por valor.

        Dos CountryCode son iguales si tienen el mismo código.
        """
        return isinstance(other, CountryCode) and self.value == other.value

    def __hash__(self) -> int:
        """Hash del objeto - Permite usar en sets y como keys de dict."""
        return hash(self.value)
