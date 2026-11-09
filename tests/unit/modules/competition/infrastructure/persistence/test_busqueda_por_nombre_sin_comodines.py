"""
Buscar competiciones por nombre trata `%` y `_` como letras, no como comodines (F-16).

La búsqueda por nombre interpolaba lo tecleado dentro del patrón
(`ILIKE f"%{x}%"`): buscar `%` devolvía todas las competiciones y `_` casaba
con cualquier carácter. Aquí se mira la SQL que se manda a PostgreSQL; el
comportamiento contra la base de datos real lo prueban los tests de integración
de `/competitions?search_name=`.
"""

from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from src.config.mappers import start_all_mappers
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)

pytestmark = pytest.mark.asyncio


class _ResultadoVacio:
    """El resultado de una consulta sin filas."""

    def scalars(self) -> "_ResultadoVacio":
        """Encadena como el resultado real."""
        return self

    def all(self) -> list[Any]:
        """Ninguna fila."""
        return []


class _SesionQueApunta:
    """Sesión falsa que se queda con la sentencia que le mandan."""

    def __init__(self) -> None:
        self.sentencia: Any = None

    async def execute(self, sentencia: Any) -> _ResultadoVacio:
        """Apunta la sentencia y no devuelve nada."""
        self.sentencia = sentencia
        return _ResultadoVacio()


async def _sql_y_parametros(search_name: str, **otros: str) -> tuple[str, dict[str, Any]]:
    """La SQL (dialecto PostgreSQL) y sus parámetros al buscar por ese nombre."""
    start_all_mappers()
    sesion = _SesionQueApunta()
    repositorio = SQLAlchemyCompetitionRepository(sesion)  # type: ignore[arg-type]

    await repositorio.find_by_filters(search_name=search_name or None, **otros)

    compilada = sesion.sentencia.compile(dialect=postgresql.dialect())
    return str(compilada), compilada.params


async def test_un_porcentaje_se_busca_escapado():
    """
    Given: una búsqueda por nombre de `%`
    When: se construye la consulta
    Then: el `%` va escapado en el patrón y la SQL declara su ESCAPE
    """
    sql, parametros = await _sql_y_parametros("%")

    assert "ESCAPE '/'" in sql
    assert "/%" in parametros.values()


async def test_un_guion_bajo_se_busca_escapado():
    """
    Given: una búsqueda por nombre de `_`
    When: se construye la consulta
    Then: el `_` va escapado en el patrón
    """
    _, parametros = await _sql_y_parametros("_")

    assert "/_" in parametros.values()


async def test_la_busqueda_sigue_sin_distinguir_mayusculas():
    """
    Given: una búsqueda por nombre de `Ávila`
    When: se construye la consulta
    Then: ILIKE con el texto tal cual: las mayúsculas (también las acentuadas) las
          compara la base de datos a los dos lados, y no Python en uno y LOWER en el
          otro (/code-review de la fase 2)
    """
    sql, parametros = await _sql_y_parametros("Ávila")

    assert "competitions.name ILIKE" in sql
    assert "Ávila" in parametros.values()
    assert "lower(" not in sql


async def test_las_ramas_del_creador_tambien_usan_ilike_escapado():
    """
    Given: una búsqueda por creador de `Á%`
    When: se construye la consulta
    Then: nombre, apellido y alias van con ILIKE, escapados y sin LOWER
    """
    sql, parametros = await _sql_y_parametros("", search_creator="Á%")

    for columna in ("users.first_name", "users.last_name", "users.alias"):
        assert f"{columna} ILIKE" in sql
    assert sql.count("ESCAPE '/'") == 3  # las tres ramas
    assert "Á/%" in parametros.values()
    assert "lower(" not in sql
