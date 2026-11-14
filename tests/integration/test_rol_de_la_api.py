"""
El usuario de la API solo maneja filas (auditoría de la fase 6, DB-01).

`scripts/db/rol_de_la_api.sql`, ejecutado por el dueño de la base sobre una base
desechable migrada entera, y luego se entra con el usuario que crea.

    caso                                              | qué pasa
    --------------------------------------------------|----------------------------------
    R5 leer, crear, cambiar y borrar filas            | puede
    R5 DROP TABLE, CREATE TABLE, CREATE ROLE          | falla
    R5 la tabla de versiones de Alembic               | no la puede tocar
    R6 una tabla que el dueño cree después            | ya la puede usar
    R7 el script dos veces                            | no falla (se puede repetir)
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
ROL = "rydercup_app"
# Solo para esta base desechable de los tests; el rol se borra al acabar
CLAVE_DE_PRUEBA = "solo-para-el-test-" + uuid.uuid4().hex  # nosec B105 - test value


def _como_dueno(url: str, sentencia: str) -> None:
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(sentencia)
    engine.dispose()


@pytest.fixture
def base_con_el_rol(base_desechable):  # noqa: F811
    _alembic(base_desechable, "upgrade", "head")
    _como_dueno(base_desechable, SCRIPT.read_text())
    _como_dueno(base_desechable, f"ALTER ROLE {ROL} PASSWORD '{CLAVE_DE_PRUEBA}'")
    try:
        yield base_desechable
    finally:
        # El rol es de todo el servidor: DROP OWNED quita sus permisos en esta base (la
        # única donde tiene) y luego se borra, para que no quede para el siguiente test
        _como_dueno(base_desechable, f"DROP OWNED BY {ROL}; DROP ROLE {ROL}")


def _como_la_api(url: str):
    return create_engine(make_url(url).set(username=ROL, password=CLAVE_DE_PRUEBA))


def test_r5_the_api_user_can_read_and_write_rows(base_con_el_rol):
    api = _como_la_api(base_con_el_rol)
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
        assert (
            conn.execute(
                text("SELECT first_name FROM users WHERE id = :id"), {"id": user_id}
            ).scalar()
            == "Eva"
        )
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    api.dispose()


@pytest.mark.parametrize(
    "sentencia",
    [
        "DROP TABLE users CASCADE",
        "CREATE TABLE intrusa (id int)",
        "ALTER TABLE users ADD COLUMN intrusa int",
        "TRUNCATE users CASCADE",
        f"CREATE ROLE oculto_{uuid.uuid4().hex[:6]} LOGIN",
        "UPDATE alembic_version SET version_num = 'x'",
    ],
)
def test_r5_the_api_user_cannot_change_the_structure(base_con_el_rol, sentencia):
    api = _como_la_api(base_con_el_rol)
    with (
        pytest.raises(ProgrammingError, match="permission denied|must be owner"),
        api.begin() as conn,
    ):
        conn.exec_driver_sql(sentencia)
    api.dispose()


def test_r6_a_table_the_owner_creates_later_is_usable(base_con_el_rol):
    _como_dueno(base_con_el_rol, "CREATE TABLE nueva_de_una_migracion (id serial PRIMARY KEY)")

    api = _como_la_api(base_con_el_rol)
    with api.begin() as conn:
        conn.exec_driver_sql("INSERT INTO nueva_de_una_migracion DEFAULT VALUES")
        assert conn.exec_driver_sql("SELECT count(*) FROM nueva_de_una_migracion").scalar() == 1
    api.dispose()


def test_r7_the_script_can_be_run_again(base_con_el_rol):
    _como_dueno(base_con_el_rol, SCRIPT.read_text())
