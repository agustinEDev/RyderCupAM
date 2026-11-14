"""
El usuario de la API solo maneja filas (auditoría de la fase 6, DB-01 y DB-03).

`scripts/db/rol_de_la_api.sql`, ejecutado por el dueño de la base sobre una base
desechable migrada entera, y luego se entra con el usuario que crea. El rol es de todo el
servidor: cada test usa un nombre propio en lugar de `rydercup_app` y lo borra al acabar.

    caso                                              | qué pasa
    --------------------------------------------------|----------------------------------
    R5 leer, crear, cambiar y borrar filas            | puede
    R5 DROP/CREATE/ALTER/TRUNCATE, CREATE ROLE        | falla
    R5 la tabla de versiones de Alembic               | no la puede tocar
    R6 una tabla que el dueño cree después            | ya la puede usar
    R7 el script dos veces                            | no falla (se puede repetir)
    R7 sobre una base sin migrar                      | se niega (alembic_version heredaría)
    DB-03 n8n en las tablas que vengan                | ya no las lee sola; backup_ro sí
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ProgrammingError

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "db" / "rol_de_la_api.sql"
ROL_DEL_SCRIPT = "rydercup_app"
# Solo para la base desechable de los tests; el rol se borra al acabar
CLAVE_DE_PRUEBA = "solo-para-el-test-" + uuid.uuid4().hex  # nosec B105 - test value


def _como_dueno(url: str, sql: str) -> None:
    """Por el cursor crudo: sin parámetros, psycopg2 no interpreta los `%` del script."""
    engine = create_engine(url)
    crudo = engine.raw_connection()
    try:
        with crudo.cursor() as cursor:
            cursor.execute(sql)
        crudo.commit()
    finally:
        crudo.close()
        engine.dispose()


def _script(rol: str) -> str:
    return SCRIPT.read_text().replace(ROL_DEL_SCRIPT, rol)


@pytest.fixture
def rol() -> str:
    return f"app_prueba_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def base_con_el_rol(base_desechable, rol):  # noqa: F811
    _alembic(base_desechable, "upgrade", "head")
    _como_dueno(base_desechable, _script(rol))
    _como_dueno(base_desechable, f"ALTER ROLE {rol} PASSWORD '{CLAVE_DE_PRUEBA}'")
    try:
        yield base_desechable
    finally:
        # DROP OWNED quita sus permisos en esta base (la única donde tiene)
        _como_dueno(base_desechable, f"DROP OWNED BY {rol}; DROP ROLE {rol}")


def _como_la_api(url: str, rol: str):
    return create_engine(make_url(url).set(username=rol, password=CLAVE_DE_PRUEBA))


def test_the_script_creates_the_user_the_runbook_names():
    assert f"CREATE ROLE {ROL_DEL_SCRIPT} LOGIN" in SCRIPT.read_text()


def test_r5_the_api_user_can_read_and_write_rows(base_con_el_rol, rol):
    api = _como_la_api(base_con_el_rol, rol)
    user_id = str(uuid.uuid4())
    with api.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, first_name, last_name, email, created_at, updated_at) "
                "VALUES (:id, 'Ana', 'Garcia', :email, now(), now())"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        conn.execute(text("UPDATE users SET first_name = 'Eva' WHERE id = :id"), {"id": user_id})
        nombre = conn.execute(
            text("SELECT first_name FROM users WHERE id = :id"), {"id": user_id}
        ).scalar()
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    api.dispose()
    assert nombre == "Eva"


@pytest.mark.parametrize(
    "sentencia",
    [
        "DROP TABLE users CASCADE",
        "CREATE TABLE intrusa (id int)",
        "ALTER TABLE users ADD COLUMN intrusa int",
        "TRUNCATE users CASCADE",
        "CREATE ROLE oculto LOGIN",
        "UPDATE alembic_version SET version_num = 'x'",
    ],
)
def test_r5_the_api_user_cannot_change_the_structure(base_con_el_rol, rol, sentencia):
    api = _como_la_api(base_con_el_rol, rol)
    with (
        pytest.raises(ProgrammingError, match="permission denied|must be owner"),
        api.begin() as conn,
    ):
        conn.exec_driver_sql(sentencia)
    api.dispose()


def test_r6_a_table_the_owner_creates_later_is_usable(base_con_el_rol, rol):
    _como_dueno(base_con_el_rol, "CREATE TABLE nueva_de_una_migracion (id serial PRIMARY KEY)")

    api = _como_la_api(base_con_el_rol, rol)
    with api.begin() as conn:
        conn.exec_driver_sql("INSERT INTO nueva_de_una_migracion DEFAULT VALUES")
        filas = conn.exec_driver_sql("SELECT count(*) FROM nueva_de_una_migracion").scalar()
    api.dispose()
    assert filas == 1


def test_r7_the_script_can_be_run_again(base_con_el_rol, rol):
    _como_dueno(base_con_el_rol, _script(rol))


def test_r7_on_a_database_without_migrations_it_refuses(base_desechable, rol):  # noqa: F811
    with pytest.raises(Exception, match="alembic upgrade head"):
        _como_dueno(base_desechable, _script(rol))

    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        existe = conn.execute(
            text("SELECT count(*) FROM pg_roles WHERE rolname = :r"), {"r": rol}
        ).scalar()
    engine.dispose()
    assert existe == 0


def test_db03_n8n_no_longer_reads_new_tables_but_backups_do(base_desechable, rol):  # noqa: F811
    _alembic(base_desechable, "upgrade", "head")
    lectores = {"n8n_lectura": None, "backup_ro": None}
    engine = create_engine(base_desechable)
    with engine.connect() as conn:
        for lector in lectores:
            lectores[lector] = conn.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": lector}
            ).scalar()
    engine.dispose()
    creados = [lector for lector, existe in lectores.items() if not existe]
    for lector in creados:
        _como_dueno(base_desechable, f"CREATE ROLE {lector} NOLOGIN")
    try:
        _como_dueno(
            base_desechable,
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES "
            "TO n8n_lectura, backup_ro",
        )

        _como_dueno(base_desechable, _script(rol))
        _como_dueno(base_desechable, "CREATE TABLE tokens_del_futuro (id int)")

        engine = create_engine(base_desechable)
        with engine.connect() as conn:
            puede = {
                lector: conn.execute(
                    text("SELECT has_table_privilege(:r, 'tokens_del_futuro', 'SELECT')"),
                    {"r": lector},
                ).scalar()
                for lector in lectores
            }
        engine.dispose()
        assert puede == {"n8n_lectura": False, "backup_ro": True}
    finally:
        _como_dueno(base_desechable, f"DROP OWNED BY {rol}; DROP ROLE {rol}")
        for lector in lectores:
            _como_dueno(base_desechable, f"DROP OWNED BY {lector}")
        for lector in creados:
            _como_dueno(base_desechable, f"DROP ROLE {lector}")
