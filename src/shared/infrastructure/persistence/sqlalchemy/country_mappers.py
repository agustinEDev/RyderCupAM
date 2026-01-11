"""
Country Mappers - SQLAlchemy Imperative Mapping for Country entity (Shared Domain).

Este mapper es parte del shared domain y se usa en múltiples módulos.
"""

from sqlalchemy import Boolean, Column, String, Table
from sqlalchemy.types import CHAR, TypeDecorator
from src.shared.domain.entities.country import Country
from src.shared.domain.value_objects.country_code import CountryCode

# Importar registry y metadata centralizados
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata,
)


# --- TypeDecorator para CountryCode ---
class CountryCodeDecorator(TypeDecorator):
    """
    TypeDecorator para convertir CountryCode (Value Object) a/desde VARCHAR(2).

    SQLAlchemy usa esto para:
    - Guardar: CountryCode -> str (2 chars)
    - Cargar: str -> CountryCode
    """

    impl = CHAR(2)
    cache_ok = True

    def process_bind_param(self, value: CountryCode | str | None, dialect) -> str | None:
        """
        Convierte CountryCode o str a string para guardar en BD.

        Args:
            value: CountryCode, str o None

        Returns:
            str: Código de país (2 chars) o None
        """
        if isinstance(value, CountryCode):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> CountryCode | None:
        """
        Convierte string de BD a CountryCode.

        Args:
            value: String de la BD (2 chars)

        Returns:
            CountryCode: Value Object o None
        """
        if value is None:
            return None
        return CountryCode(value)


# --- Registro y Metadatos ---
# (Importados de base.py - ver imports arriba)


# --- Definición de Tabla countries ---
countries_table = Table(
    "countries",
    metadata,
    Column("code", CountryCodeDecorator, primary_key=True),
    Column("active", Boolean, nullable=False, default=True),
    Column("name_en", String(100), nullable=False),
    Column("name_es", String(100), nullable=False),
)


# --- Definición de Tabla country_adjacencies ---
country_adjacencies_table = Table(
    "country_adjacencies",
    metadata,
    Column("country_code_1", CountryCodeDecorator, primary_key=True),
    Column("country_code_2", CountryCodeDecorator, primary_key=True),
)


def start_country_mappers():
    """
    Inicia el mapeo entre la entidad Country y la tabla countries.

    Es idempotente - puede llamarse múltiples veces sin problemas.

    Note:
        - Country es una entidad de solo lectura (seed data)
        - No requiere composites porque todos los campos son primitivos
        - code es la identidad (PK)
    """
    # Verificar si el mapper ya existe
    if Country not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Country,
            countries_table,
            properties={
                # Mapeo directo - Country es un dataclass simple
                # SQLAlchemy mapea automáticamente los campos
            },
        )


def start_mappers():
    """
    Inicia los mappers de Country (shared domain).

    Esta función debe ser llamada al inicio de la aplicación (en main.py)
    para registrar los mappers de SQLAlchemy antes de realizar cualquier
    operación con la base de datos.

    Es idempotente: puede llamarse múltiples veces sin efectos adversos.
    """
    start_country_mappers()
