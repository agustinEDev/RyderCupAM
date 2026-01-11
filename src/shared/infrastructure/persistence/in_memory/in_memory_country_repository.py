"""In-Memory Country Repository para testing."""

from src.shared.domain.entities.country import Country
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.value_objects.country_code import CountryCode


class InMemoryCountryRepository(CountryRepositoryInterface):
    """
    Implementación en memoria del repositorio de países para testing.

    Incluye datos de prueba pre-cargados con países europeos comunes.
    """

    def __init__(self):
        self._countries: dict[CountryCode, Country] = {}
        # Definir adyacencias (países fronterizos)
        self._adjacencies: dict[CountryCode, set[CountryCode]] = {}
        self._load_test_data()

    def _load_test_data(self):
        """Carga datos de prueba con países europeos y sus adyacencias."""
        # Crear países de prueba
        spain = Country(CountryCode("ES"), "Spain", "España")
        portugal = Country(CountryCode("PT"), "Portugal", "Portugal")
        france = Country(CountryCode("FR"), "France", "Francia")
        italy = Country(CountryCode("IT"), "Italy", "Italia")
        germany = Country(CountryCode("DE"), "Germany", "Alemania")
        uk = Country(CountryCode("GB"), "United Kingdom", "Reino Unido")

        # Guardar países
        for country in [spain, portugal, france, italy, germany, uk]:
            self._countries[country.code] = country

        # Definir adyacencias (países fronterizos)
        self._adjacencies = {
            CountryCode("ES"): {CountryCode("PT"), CountryCode("FR")},
            CountryCode("PT"): {CountryCode("ES")},
            CountryCode("FR"): {
                CountryCode("ES"),
                CountryCode("IT"),
                CountryCode("DE"),
                CountryCode("GB"),
            },
            CountryCode("IT"): {CountryCode("FR")},
            CountryCode("DE"): {CountryCode("FR")},
            CountryCode("GB"): {CountryCode("FR")},  # Túnel del Canal
        }

    async def find_by_code(self, code: CountryCode) -> Country | None:
        """Busca un país por su código."""
        return self._countries.get(code)

    async def find_all_active(self) -> list[Country]:
        """Retorna todos los países activos."""
        return [country for country in self._countries.values() if country.is_active()]

    async def are_adjacent(self, country1: CountryCode, country2: CountryCode) -> bool:
        """Verifica si dos países son adyacentes (comparten frontera)."""
        if country1 not in self._adjacencies:
            return False

        return country2 in self._adjacencies[country1]

    async def find_adjacent_countries(self, country_code: CountryCode) -> list[Country]:
        """Busca todos los países adyacentes a un país dado."""
        if country_code not in self._adjacencies:
            return []

        adjacent_codes = self._adjacencies[country_code]
        return [self._countries[code] for code in adjacent_codes if code in self._countries]

    async def save(self, country: Country) -> None:
        """Guarda o actualiza un país (para testing)."""
        self._countries[country.code] = country

    async def exists(self, code: CountryCode) -> bool:
        """Verifica si existe un país con el código especificado."""
        return code in self._countries

    def add_adjacency(self, country1: CountryCode, country2: CountryCode) -> None:
        """
        Añade una adyacencia entre dos países (helper para tests).

        La adyacencia es bidireccional.
        """
        if country1 not in self._adjacencies:
            self._adjacencies[country1] = set()
        if country2 not in self._adjacencies:
            self._adjacencies[country2] = set()

        self._adjacencies[country1].add(country2)
        self._adjacencies[country2].add(country1)
