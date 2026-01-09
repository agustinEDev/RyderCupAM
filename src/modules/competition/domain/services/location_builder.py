"""
LocationBuilder - Domain Service.

Servicio de dominio para construir y validar el Value Object Location.
Encapsula la lógica de validación de países y adyacencias.
"""

from src.modules.competition.domain.value_objects.location import Location
from src.shared.domain.repositories.country_repository_interface import CountryRepositoryInterface
from src.shared.domain.value_objects.country_code import CountryCode


class InvalidCountryError(Exception):
    """Excepción lanzada cuando un país no existe o no es válido."""

    pass


class LocationBuilder:
    """
    Servicio de dominio para construir Location con validaciones.

    Responsabilidades:
    - Validar que los países existan en la base de datos
    - Validar que los países adyacentes sean realmente adyacentes al principal
    - Construir el Value Object Location correctamente

    Este servicio encapsula lógica de dominio que requiere acceso a repositorios,
    siguiendo el patrón Domain Service de DDD.

    Ejemplo de uso:
        location_builder = LocationBuilder(country_repository)
        location = await location_builder.build_from_codes("ES", "PT", "FR")
    """

    def __init__(self, country_repository: CountryRepositoryInterface):
        """
        Constructor.

        Args:
            country_repository: Repositorio para acceder a datos de países
        """
        self._country_repo = country_repository

    async def build_from_codes(
        self,
        main_country: str,
        adjacent_country_1: str | None = None,
        adjacent_country_2: str | None = None,
    ) -> Location:
        """
        Construye un Location validando países y adyacencias.

        Args:
            main_country: Código ISO del país principal (ej: "ES")
            adjacent_country_1: Código ISO del país adyacente 1 (opcional)
            adjacent_country_2: Código ISO del país adyacente 2 (opcional)

        Returns:
            Location: Value Object con países validados

        Raises:
            InvalidCountryError: Si algún país no existe o no es adyacente
            ValueError: Si los códigos de país no son válidos (from CountryCode)
        """
        # 1. Validar y obtener país principal
        main_code = CountryCode(main_country)
        await self._validate_country_exists(main_code)

        # 2. Construir lista de países adyacentes validados
        adjacent_codes = []

        if adjacent_country_1:
            adj1_code = CountryCode(adjacent_country_1)
            await self._validate_country_exists(adj1_code)
            await self._validate_adjacency(main_code, adj1_code)
            adjacent_codes.append(adj1_code)

        if adjacent_country_2:
            adj2_code = CountryCode(adjacent_country_2)
            await self._validate_country_exists(adj2_code)
            await self._validate_adjacency(main_code, adj2_code)
            adjacent_codes.append(adj2_code)

        # 3. Construir Location según número de países adyacentes
        if len(adjacent_codes) == 0:
            return Location(main_code)
        if len(adjacent_codes) == 1:
            return Location(main_code, adjacent_codes[0])
        return Location(main_code, adjacent_codes[0], adjacent_codes[1])

    async def _validate_country_exists(self, country_code: CountryCode) -> None:
        """
        Valida que un país exista en la base de datos.

        Args:
            country_code: Código del país a validar

        Raises:
            InvalidCountryError: Si el país no existe
        """
        country = await self._country_repo.find_by_code(country_code)
        if not country:
            raise InvalidCountryError(f"El país con código '{country_code.value}' no existe")

    async def _validate_adjacency(
        self, main_country: CountryCode, adjacent_country: CountryCode
    ) -> None:
        """
        Valida que dos países sean adyacentes.

        Args:
            main_country: Código del país principal
            adjacent_country: Código del país adyacente a validar

        Raises:
            InvalidCountryError: Si los países no son adyacentes
        """
        is_adjacent = await self._country_repo.are_adjacent(main_country, adjacent_country)

        if not is_adjacent:
            raise InvalidCountryError(
                f"El país '{adjacent_country.value}' no es adyacente a '{main_country.value}'"
            )
