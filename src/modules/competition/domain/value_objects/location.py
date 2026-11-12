"""
Location Value Object - Ubicación geográfica de una competición.

Este Value Object representa la localización del torneo usando códigos ISO de países.
Permite torneos en un país o en zonas fronterizas (hasta 3 países).

La validación de adyacencia real se realiza en la capa de aplicación (Use Case),
no en este VO, para mantener la separación de responsabilidades.
"""

from dataclasses import dataclass
from typing import Any

from src.shared.domain.value_objects.country_code import CountryCode


class InvalidLocationError(Exception):
    """Excepción lanzada cuando la ubicación no es válida."""

    pass


@dataclass(frozen=True)
class Location:
    """
    Value Object para ubicación geográfica.

    Inmutable y validado automáticamente.
    Representa la localización de un torneo de golf usando códigos ISO.

    Reglas de negocio:
    - main_country es obligatorio
    - adjacent_country_1 y adjacent_country_2 son opcionales
    - Los países no pueden repetirse
    - No puede haber adjacent_country_2 sin adjacent_country_1 (orden)

    IMPORTANTE:
    Este VO NO valida si los países son realmente adyacentes geográficamente.
    Esa validación se realiza en el Use Case consultando la tabla de adyacencias.

    Ejemplos:
        >>> from src.shared.domain.value_objects.country_code import CountryCode
        >>>
        >>> # Torneo en un solo país
        >>> loc1 = Location(CountryCode("ES"))
        >>> print(loc1)
        'ES'

        >>> # Torneo en frontera España-Portugal
        >>> loc2 = Location(CountryCode("ES"), CountryCode("PT"))
        >>> loc2.get_all_countries()
        [CountryCode("ES"), CountryCode("PT")]

        >>> # Inválido: países duplicados
        >>> Location(CountryCode("ES"), CountryCode("ES"))  # Lanza InvalidLocationError

        >>> # Inválido: adjacent_country_2 sin adjacent_country_1
        >>> Location(CountryCode("ES"), None, CountryCode("FR"))  # Lanza InvalidLocationError
    """

    main_country: CountryCode
    adjacent_country_1: CountryCode | None = None
    adjacent_country_2: CountryCode | None = None

    def __post_init__(self) -> None:
        """
        Validación automática de la ubicación.

        Valida reglas de negocio estructurales (no geográficas).
        """
        # 1. Validar que main_country no sea None
        if self.main_country is None:
            raise InvalidLocationError("El país principal no puede ser None")

        # 2. Validar que adjacent_country_2 no exista sin adjacent_country_1
        if self.adjacent_country_2 is not None and self.adjacent_country_1 is None:
            raise InvalidLocationError(
                "No puede existir adjacent_country_2 sin adjacent_country_1. "
                "Debe mantener el orden: main → adj1 → adj2"
            )

        # 3. Validar que no haya países duplicados
        countries = [self.main_country]
        if self.adjacent_country_1:
            countries.append(self.adjacent_country_1)
        if self.adjacent_country_2:
            countries.append(self.adjacent_country_2)

        # Convertir a set para detectar duplicados
        unique_countries = set(countries)
        if len(countries) != len(unique_countries):
            country_codes = [c.value for c in countries]
            raise InvalidLocationError(
                f"Los países no pueden repetirse. Se encontraron: {country_codes}"
            )

    def get_all_countries(self) -> list[CountryCode]:
        """
        Obtiene la lista de todos los códigos de países involucrados.

        Returns:
            List[CountryCode]: Lista de países (siempre al menos 1)

        Ejemplos:
            >>> loc = Location(CountryCode("ES"), CountryCode("PT"))
            >>> loc.get_all_countries()
            [CountryCode("ES"), CountryCode("PT")]
        """
        countries = [self.main_country]
        if self.adjacent_country_1:
            countries.append(self.adjacent_country_1)
        if self.adjacent_country_2:
            countries.append(self.adjacent_country_2)
        return countries

    def __str__(self) -> str:
        """
        Representación string legible.

        Formatos:
        - Un país: "ES"
        - Dos países: "ES / PT"
        - Tres países: "ES / PT / FR"
        """
        country_codes = [c.value for c in self.get_all_countries()]
        return " / ".join(country_codes)

    def __eq__(self, other: object) -> bool:
        """
        Operador de igualdad - Comparación por valor.

        Dos Location son iguales si tienen los mismos países en el mismo orden.
        """
        return (
            isinstance(other, Location)
            and self.main_country == other.main_country
            and self.adjacent_country_1 == other.adjacent_country_1
            and self.adjacent_country_2 == other.adjacent_country_2
        )

    def __hash__(self) -> int:
        """Hash del objeto - Permite usar en sets y como keys de dict."""
        return hash((self.main_country, self.adjacent_country_1, self.adjacent_country_2))

    def __composite_values__(self) -> tuple[Any, ...]:
        """
        Retorna los valores para SQLAlchemy composite mapping.

        Requerido para que SQLAlchemy pueda persistir el Value Object.
        """
        return (self.main_country, self.adjacent_country_1, self.adjacent_country_2)
