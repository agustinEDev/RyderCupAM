"""
Country Mappers - SQLAlchemy Imperative Mapping for Country entity (Shared Domain).

Este mapper es parte del shared domain y se usa en múltiples módulos.
"""

from sqlalchemy import Boolean, Column, ForeignKey, String, Table, inspect

from src.shared.domain.entities.country import Country

# Importar registry y metadata centralizados
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata,
)
from src.shared.infrastructure.persistence.sqlalchemy.tipos_de_id import tipo_de_codigo_de_pais

# --- TypeDecorator para CountryCode ---
CountryCodeDecorator = tipo_de_codigo_de_pais()


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
    Column(
        "country_code_1",
        CountryCodeDecorator,
        ForeignKey("countries.code", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "country_code_2",
        CountryCodeDecorator,
        ForeignKey("countries.code", ondelete="CASCADE"),
        primary_key=True,
    ),
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
    if inspect(Country, raiseerr=False) is None:
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
