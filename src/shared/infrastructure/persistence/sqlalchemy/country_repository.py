"""
Country Repository - SQLAlchemy Implementation (Shared Domain).

Implementación concreta del repositorio de países usando SQLAlchemy async.
Este es un repositorio de solo lectura para datos de referencia (seed data).
"""

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.domain.entities.country import Country
from src.shared.domain.repositories.country_repository_interface import (
    CountryRepositoryInterface,
)
from src.shared.domain.value_objects.country_code import CountryCode

# Import de la tabla country_adjacencies para queries de adyacencia
from src.shared.infrastructure.persistence.sqlalchemy.country_mappers import (
    country_adjacencies_table,
)


class SQLAlchemyCountryRepository(CountryRepositoryInterface):
    """
    Implementación asíncrona del repositorio de países con SQLAlchemy.

    Repositorio de solo lectura para datos de referencia (países y fronteras).
    Los países se cargan mediante seeds, no se crean/modifican por usuarios.
    """

    def __init__(self, session: AsyncSession):
        """
        Constructor del repositorio.

        Args:
            session: Sesión asíncrona de SQLAlchemy
        """
        self._session = session

    async def find_by_code(self, code: CountryCode) -> Country | None:
        """
        Busca un país por su código ISO.

        Args:
            code: Código del país (ej: CountryCode("ES"))

        Returns:
            Optional[Country]: El país encontrado o None
        """
        return await self._session.get(Country, code)

    async def find_all_active(self) -> list[Country]:
        """
        Obtiene todos los países activos.

        Útil para poblar dropdowns en frontend.

        Returns:
            List[Country]: Lista de países activos ordenados alfabéticamente por nombre en inglés
        """
        statement = select(Country).where(Country.active).order_by(Country.name_en.asc())
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def are_adjacent(self, country1: CountryCode, country2: CountryCode) -> bool:
        """
        Verifica si dos países son adyacentes (comparten frontera).

        La tabla country_adjacencies almacena las relaciones bidireccionales:
        - (ES, PT) y (PT, ES) están ambas almacenadas
        - Por eso buscamos en una sola dirección

        Args:
            country1: Código del primer país
            country2: Código del segundo país

        Returns:
            bool: True si son adyacentes, False si no lo son

        Examples:
            >>> await repo.are_adjacent(CountryCode("ES"), CountryCode("PT"))
            True
            >>> await repo.are_adjacent(CountryCode("ES"), CountryCode("JP"))
            False
        """
        # Como las relaciones están duplicadas bidireccionalmente,
        # solo necesitamos buscar en una dirección
        statement = (
            select(func.count())
            .select_from(country_adjacencies_table)
            .where(
                country_adjacencies_table.c.country_code_1 == country1,
                country_adjacencies_table.c.country_code_2 == country2,
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one() > 0

    async def find_adjacent_countries(self, code: CountryCode) -> list[Country]:
        """
        Obtiene todos los países adyacentes a un país dado.

        Join entre country_adjacencies y countries para obtener los detalles
        completos de los países vecinos.

        Args:
            code: Código del país

        Returns:
            List[Country]: Lista de países adyacentes ordenados alfabéticamente

        Examples:
            >>> adjacent = await repo.find_adjacent_countries(CountryCode("ES"))
            >>> # Retorna: [Andorra, Francia, Gibraltar, Marruecos, Portugal]
        """
        # Join: country_adjacencies → countries
        # WHERE country_code_1 = 'ES'
        # Esto nos da todos los country_code_2 que son adyacentes
        statement = (
            select(Country)
            .join(
                country_adjacencies_table,
                Country.code == country_adjacencies_table.c.country_code_2,
            )
            .where(country_adjacencies_table.c.country_code_1 == code)
            .where(Country.active)
            .order_by(Country.name_en.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def exists(self, code: CountryCode) -> bool:
        """
        Verifica si existe un país con el código especificado.

        Args:
            code: Código del país

        Returns:
            bool: True si existe, False si no existe
        """
        statement = select(func.count()).select_from(Country).where(Country.code == code)
        result = await self._session.execute(statement)
        return result.scalar_one() > 0
