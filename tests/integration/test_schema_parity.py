"""Paridad entre los mappers de SQLAlchemy y el esquema real de Alembic.

Los tests construyen su esquema con `metadata.create_all()` (los mappers),
mientras que producción corre el esquema que producen las migraciones. Cuando
los dos discrepan, la suite valida un esquema que no existe en ningún sitio.

Eso fue exactamente lo que dejó pasar el bug #154: las FKs de `invitations`
hacia `users` declaraban CASCADE/SET NULL en el mapper pero ningún `ON DELETE`
en la migración, así que en tests las invitaciones cascadeaban y en producción
el borrado de un usuario abortaba con ForeignKeyViolationError.

Ver #156.
"""

import os
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.conftest import DATABASE_URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ASYNCPG_DRIVER = "postgresql+asyncpg"
PSYCOPG2_DRIVER = "postgresql+psycopg2"

# Postgres representa "sin ON DELETE" como NO ACTION; los mappers lo representan
# como ondelete=None. Se normalizan a None para poder compararlos.
_NO_ACTION = {None, "", "NO ACTION"}


def _sync_url(url: str) -> str:
    return url.replace(ASYNCPG_DRIVER, PSYCOPG2_DRIVER)


def _normalize_ondelete(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return None if normalized in _NO_ACTION else normalized


@pytest.fixture(scope="module")
def migrated_schema():
    """Crea una BD temporal, le aplica `alembic upgrade head` y la inspecciona."""
    base_url = _sync_url(DATABASE_URL).rsplit("/", 1)[0]
    db_name = f"test_parity_{uuid.uuid4().hex[:8]}"

    admin_engine = create_engine(f"{base_url}/postgres", isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        conn.execute(text(f"CREATE DATABASE {db_name}"))
    admin_engine.dispose()

    target_url = f"{base_url}/{db_name}"
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=PROJECT_ROOT,
            env={**os.environ, "DATABASE_URL": target_url},
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail(
                "`alembic upgrade head` falló sobre una base de datos limpia:\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

        engine = create_engine(target_url)
        yield engine
        engine.dispose()
    finally:
        admin_engine = create_engine(f"{base_url}/postgres", isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": db_name},
            )
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        admin_engine.dispose()


def _mapper_foreign_keys() -> dict[tuple[str, tuple[str, ...]], str | None]:
    """FKs declaradas por los mappers, indexadas por (tabla, columnas origen)."""
    from src.shared.infrastructure.persistence.sqlalchemy.base import metadata

    declared: dict[tuple[str, tuple[str, ...]], str | None] = {}
    for table in metadata.tables.values():
        for constraint in table.foreign_key_constraints:
            columns = tuple(sorted(col.name for col in constraint.columns))
            declared[(table.name, columns)] = _normalize_ondelete(constraint.ondelete)
    return declared


def _migrated_foreign_keys(engine) -> dict[tuple[str, tuple[str, ...]], str | None]:
    """FKs presentes en el esquema que produce Alembic."""
    inspector = inspect(engine)
    actual: dict[tuple[str, tuple[str, ...]], str | None] = {}
    for table_name in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table_name):
            columns = tuple(sorted(fk["constrained_columns"]))
            ondelete = (fk.get("options") or {}).get("ondelete")
            actual[(table_name, columns)] = _normalize_ondelete(ondelete)
    return actual


def _format(entries) -> str:
    return "\n".join(f"  - {line}" for line in sorted(entries))


class TestSchemaParity:
    """Los mappers y las migraciones deben describir el mismo esquema."""

    def test_foreign_key_ondelete_rules_match(self, migrated_schema):
        """Cada FK debe declarar el mismo ON DELETE en el mapper y en la migración.

        Es la comprobación que habría cazado #154: `invitations.invitee_user_id`
        declaraba SET NULL en el mapper y nada en la migración.
        """
        declared = _mapper_foreign_keys()
        actual = _migrated_foreign_keys(migrated_schema)

        mismatches = [
            f"{table}.{', '.join(columns)}: mapper={declared[(table, columns)] or 'ninguno'} "
            f"vs migración={actual[(table, columns)] or 'ninguno'}"
            for (table, columns) in declared.keys() & actual.keys()
            if declared[(table, columns)] != actual[(table, columns)]
        ]

        assert not mismatches, (
            "Los mappers y las migraciones declaran reglas ON DELETE distintas. "
            "La suite construye su esquema desde los mappers, así que estas FKs se "
            "comportan de una forma en tests y de otra en producción:\n"
            f"{_format(mismatches)}"
        )

    def test_no_foreign_keys_missing_from_either_side(self, migrated_schema):
        """Ninguna FK debe existir solo en los mappers o solo en las migraciones."""
        declared = _mapper_foreign_keys()
        actual = _migrated_foreign_keys(migrated_schema)

        only_in_mappers = [
            f"{table}.{', '.join(columns)}" for (table, columns) in declared.keys() - actual.keys()
        ]
        only_in_migrations = [
            f"{table}.{', '.join(columns)}" for (table, columns) in actual.keys() - declared.keys()
        ]

        problems = []
        if only_in_mappers:
            problems.append(
                "FKs declaradas en los mappers que ninguna migración crea:\n"
                f"{_format(only_in_mappers)}"
            )
        if only_in_migrations:
            problems.append(
                "FKs creadas por las migraciones que los mappers no declaran:\n"
                f"{_format(only_in_migrations)}"
            )

        assert not problems, "\n\n".join(problems)

    def test_no_tables_missing_from_either_side(self, migrated_schema):
        """Los mappers y las migraciones deben definir el mismo conjunto de tablas."""
        from src.shared.infrastructure.persistence.sqlalchemy.base import metadata

        mapper_tables = set(metadata.tables.keys())
        migrated_tables = set(inspect(migrated_schema).get_table_names()) - {"alembic_version"}

        problems = []
        if mapper_tables - migrated_tables:
            problems.append(
                f"Tablas en los mappers que ninguna migración crea:\n"
                f"{_format(mapper_tables - migrated_tables)}"
            )
        if migrated_tables - mapper_tables:
            problems.append(
                f"Tablas creadas por las migraciones que ningún mapper declara:\n"
                f"{_format(migrated_tables - mapper_tables)}"
            )

        assert not problems, "\n\n".join(problems)
