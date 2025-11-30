"""
Country Repository Interface - Shared Domain Layer

Define el contrato para consulta de países y validación de adyacencia.
Esta interfaz pertenece al shared domain y será implementada en la capa de infraestructura.

Nota: Countries son datos de referencia (seed data), por lo que este repositorio
es principalmente de solo lectura. No se espera que los usuarios creen/modifiquen países.
"""

from abc import ABC, abstractmethod

from ..entities.country import Country
from ..value_objects.country_code import CountryCode


class CountryRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de países.

    Define operaciones de consulta para países y validación de adyacencia.
    Este es un repositorio de solo lectura para datos de referencia.

    Principios seguidos:
    - Dependency Inversion: El dominio define el contrato, infraestructura lo implementa
    - Single Responsibility: Solo operaciones relacionadas con consulta de países
    - Interface Segregation: Métodos específicos y cohesivos
    """

    @abstractmethod
    async def find_by_code(self, code: CountryCode) -> Country | None:
        """
        Busca un país por su código ISO 3166-1 alpha-2.

        Args:
            code: El código del país (ej: CountryCode("ES"))

        Returns:
            Optional[Country]: El país encontrado o None si no existe

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def find_all_active(self) -> list[Country]:
        """
        Obtiene todos los países activos.

        Útil para: Poblar dropdown de países en frontend.

        Returns:
            List[Country]: Lista de todos los países activos

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass

    @abstractmethod
    async def are_adjacent(
        self,
        country1: CountryCode,
        country2: CountryCode
    ) -> bool:
        """
        Verifica si dos países son adyacentes (comparten frontera).

        Útil para: Validación en CreateCompetitionUseCase al especificar Location.

        Args:
            country1: El código del primer país
            country2: El código del segundo país

        Returns:
            bool: True si son adyacentes, False si no lo son

        Raises:
            RepositoryError: Si ocurre un error de consulta

        Ejemplos:
            >>> await repo.are_adjacent(CountryCode("ES"), CountryCode("PT"))
            True
            >>> await repo.are_adjacent(CountryCode("ES"), CountryCode("DE"))
            False
        """
        pass

    @abstractmethod
    async def find_adjacent_countries(self, code: CountryCode) -> list[Country]:
        """
        Obtiene todos los países adyacentes a un país dado.

        Útil para: Pre-filtrar opciones de países adyacentes en frontend.

        Args:
            code: El código del país

        Returns:
            List[Country]: Lista de países adyacentes

        Raises:
            RepositoryError: Si ocurre un error de consulta

        Ejemplos:
            >>> adjacent = await repo.find_adjacent_countries(CountryCode("ES"))
            >>> # Retorna: [Country(PT), Country(FR), Country(AD)]
        """
        pass

    @abstractmethod
    async def exists(self, code: CountryCode) -> bool:
        """
        Verifica si existe un país con el código especificado.

        Útil para: Validación rápida antes de crear Location.

        Args:
            code: El código del país

        Returns:
            bool: True si existe, False si no existe

        Raises:
            RepositoryError: Si ocurre un error de consulta
        """
        pass
