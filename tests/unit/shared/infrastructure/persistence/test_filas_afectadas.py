"""Las filas que tocó una sentencia, sin suponer el tipo del resultado."""

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, delete, insert, select

from src.shared.infrastructure.persistence.filas_afectadas import filas_afectadas

_metadata = MetaData()
_tabla = Table("filas", _metadata, Column("id", Integer, primary_key=True))


def _conexion_con_tres_filas():
    engine = create_engine("sqlite://")
    _metadata.create_all(engine)
    conexion = engine.connect()
    conexion.execute(insert(_tabla), [{"id": 1}, {"id": 2}, {"id": 3}])
    return conexion


def test_filas_afectadas_after_a_delete_returns_its_rowcount():
    """
    Given: A table with three rows
    When: Deleting two of them
    Then: Two rows were affected
    """
    with _conexion_con_tres_filas() as conexion:
        result = conexion.execute(delete(_tabla).where(_tabla.c.id < 3))

        assert filas_afectadas(result) == 2


def test_filas_afectadas_with_a_result_without_cursor_fails_as_reading_rowcount_did():
    """
    Given: A result that is not a cursor one (a frozen SELECT replayed)
    When: Asking for its affected rows
    Then: The same AttributeError as reading `.rowcount` directly (no new failure)
    """
    with _conexion_con_tres_filas() as conexion:
        sin_cursor = conexion.execute(select(_tabla)).freeze()()

        with pytest.raises(AttributeError):
            filas_afectadas(sin_cursor)
