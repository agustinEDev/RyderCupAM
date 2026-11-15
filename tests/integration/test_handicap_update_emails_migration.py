"""
La migración de los correos de las actualizaciones ya enviados (f9b1d3e5a7c9, D2).

| Caso                                     | Resultado                                        |
|------------------------------------------|--------------------------------------------------|
| Subir sobre una base de la versión antes | La tabla nace vacía, con sus columnas            |
| La clave                                 | (competición, usuario, tipo): un correo por tipo |
| Las claves ajenas                        | Con borrado en cascada (competición y usuario)   |
| Bajar                                    | La tabla desaparece                              |
"""

from sqlalchemy import create_engine, text

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

ANTERIOR = "e7b9d1f3a5c2"
CORREOS = "f9b1d3e5a7c9"


def _consulta(url: str, sql: str):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql)).all()
    finally:
        engine.dispose()


def test_nace_vacia_con_su_clave_y_sus_cascadas(base_desechable):  # noqa: F811
    """
    Given una base de la versión anterior
    When se sube la migración
    Then la tabla está vacía, con clave (competición, usuario, tipo) y cascadas
    """
    _alembic(base_desechable, "upgrade", ANTERIOR)

    _alembic(base_desechable, "upgrade", CORREOS)

    assert _consulta(base_desechable, "SELECT count(*) FROM handicap_update_emails") == [(0,)]
    columnas = _consulta(
        base_desechable,
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_name = 'handicap_update_emails' ORDER BY ordinal_position",
    )
    assert columnas == [
        ("competition_id", "NO"),
        ("user_id", "NO"),
        ("kind", "NO"),
        ("fingerprint", "NO"),
        ("sent_at", "NO"),
    ]
    clave = _consulta(
        base_desechable,
        "SELECT a.attname FROM pg_index i "
        "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE i.indrelid = 'handicap_update_emails'::regclass AND i.indisprimary "
        "ORDER BY a.attname",
    )
    assert [c for (c,) in clave] == ["competition_id", "kind", "user_id"]
    cascadas = _consulta(
        base_desechable,
        "SELECT confrelid::regclass::text, confdeltype FROM pg_constraint "
        "WHERE conrelid = 'handicap_update_emails'::regclass AND contype = 'f' "
        "ORDER BY 1",
    )
    assert cascadas == [("competitions", "c"), ("users", "c")]


def test_bajar_quita_la_tabla(base_desechable):  # noqa: F811
    """Given la migración subida When se baja Then la tabla ya no existe."""
    _alembic(base_desechable, "upgrade", CORREOS)

    _alembic(base_desechable, "downgrade", ANTERIOR)

    assert _consulta(
        base_desechable, "SELECT to_regclass('public.handicap_update_emails') IS NULL"
    ) == [(True,)]
