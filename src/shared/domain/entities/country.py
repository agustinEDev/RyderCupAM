# -*- coding: utf-8 -*-
"""
Country Entity - Representa un país en el sistema.

Entidad de dominio compartida para gestión de países con soporte multilenguaje.
"""

from dataclasses import dataclass
from ..value_objects.country_code import CountryCode


@dataclass
class Country:
    """
    Entidad Country - Representa un país.

    Un país es identificado por su código ISO 3166-1 alpha-2.
    Contiene nombres en múltiples idiomas para soporte i18n.

    Esta entidad es de solo lectura en el dominio (managed data).
    Los países se cargan mediante seeds, no se crean dinámicamente.

    Atributos:
        code: Código ISO del país (identidad única)
        name_en: Nombre en inglés
        name_es: Nombre en español
        active: Si el país está activo para selección

    Ejemplos:
        >>> spain = Country(
        ...     code=CountryCode("ES"),
        ...     name_en="Spain",
        ...     name_es="España",
        ...     active=True
        ... )
        >>> print(spain.get_name("es"))
        'España'
        >>> print(spain.get_name("en"))
        'Spain'
    """

    code: CountryCode
    name_en: str
    name_es: str
    active: bool = True

    def get_name(self, language: str = "en") -> str:
        """
        Obtiene el nombre del país en el idioma especificado.

        Args:
            language: Código de idioma ("en", "es"). Default: "en"

        Returns:
            str: Nombre del país en el idioma solicitado

        Ejemplos:
            >>> spain = Country(CountryCode("ES"), "Spain", "España")
            >>> spain.get_name("es")
            'España'
            >>> spain.get_name("en")
            'Spain'
            >>> spain.get_name("fr")  # Fallback a inglés
            'Spain'
        """
        language_map = {
            "en": self.name_en,
            "es": self.name_es,
        }

        # Fallback a inglés si el idioma no está soportado
        return language_map.get(language, self.name_en)

    def is_active(self) -> bool:
        """
        Verifica si el país está activo para selección.

        Returns:
            bool: True si está activo, False en caso contrario
        """
        return self.active

    def __str__(self) -> str:
        """Representación string legible."""
        return f"{self.code} - {self.name_en}"

    def __eq__(self, other) -> bool:
        """
        Operador de igualdad - Comparación por identidad (code).

        Dos países son iguales si tienen el mismo código.
        """
        return isinstance(other, Country) and self.code == other.code

    def __hash__(self) -> int:
        """Hash del objeto basado en el código."""
        return hash(self.code)
