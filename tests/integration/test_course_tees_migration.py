"""
La migración de las barras por campo (a7e3c5d9b1f4, 20 nov 2026).

| Caso                                     | Resultado                                         |
|------------------------------------------|---------------------------------------------------|
| Subir sobre la versión anterior          | Las dos tablas nacen vacías                       |
| Las claves                               | (inscripción, campo) y (competición, campo, género) |
| Las claves ajenas                        | Con borrado en cascada                            |
| Bajar                                    | Las dos tablas desaparecen                        |
"""

from sqlalchemy import create_engine, text

from tests.integration.test_activity_events_published_at_migration import (
    _alembic,
    base_desechable,  # noqa: F401
)

ANTERIOR = "b29a88392439"
BARRAS = "a7e3c5d9b1f4"


def _consulta(url: str, sql: str):
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql)).all()
    finally:
        engine.dispose()


def test_nacen_vacias_con_sus_claves_y_sus_cascadas(base_desechable):  # noqa: F811
    """
    Given una base de la versión anterior
    When se sube la migración
    Then las dos tablas están vacías, con sus claves primarias y cascadas
    """
    _alembic(base_desechable, "upgrade", ANTERIOR)

    _alembic(base_desechable, "upgrade", BARRAS)

    for tabla in ("enrollment_course_tees", "competition_course_tees"):
        assert _consulta(base_desechable, f"SELECT count(*) FROM {tabla}") == [(0,)]
    claves = _consulta(
        base_desechable,
        "SELECT tc.table_name, kcu.column_name FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name "
        "WHERE tc.constraint_type = 'PRIMARY KEY' "
        "AND tc.table_name IN ('enrollment_course_tees', 'competition_course_tees') "
        "ORDER BY tc.table_name, kcu.ordinal_position",
    )
    assert claves == [
        ("competition_course_tees", "competition_id"),
        ("competition_course_tees", "golf_course_id"),
        ("competition_course_tees", "gender"),
        ("enrollment_course_tees", "enrollment_id"),
        ("enrollment_course_tees", "golf_course_id"),
    ]
    cascadas = _consulta(
        base_desechable,
        "SELECT rc.delete_rule FROM information_schema.referential_constraints rc "
        "JOIN information_schema.table_constraints tc ON rc.constraint_name = tc.constraint_name "
        "WHERE tc.table_name IN ('enrollment_course_tees', 'competition_course_tees')",
    )
    assert {fila[0] for fila in cascadas} == {"CASCADE"} and len(cascadas) == 4
    indices = _consulta(
        base_desechable,
        "SELECT indexname FROM pg_indexes "
        "WHERE indexname LIKE 'ix_%_course_tees_golf_course_id' ORDER BY indexname",
    )
    assert indices == [
        ("ix_competition_course_tees_golf_course_id",),
        ("ix_enrollment_course_tees_golf_course_id",),
    ]


def test_el_genero_de_la_barra_del_campo_solo_es_male_o_female(base_desechable):  # noqa: F811
    """
    Given la migración subida
    When se mira la restricción del género de competition_course_tees
    Then solo admite MALE o FEMALE
    """
    _alembic(base_desechable, "upgrade", BARRAS)

    [(definicion,)] = _consulta(
        base_desechable,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'ck_competition_course_tees_gender'",
    )
    assert "MALE" in definicion and "FEMALE" in definicion


def test_bajar_quita_las_dos_tablas(base_desechable):  # noqa: F811
    """
    Given la base con la migración
    When se baja a la versión anterior
    Then las dos tablas desaparecen
    """
    _alembic(base_desechable, "upgrade", BARRAS)

    _alembic(base_desechable, "downgrade", ANTERIOR)

    tablas = _consulta(
        base_desechable,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name IN ('enrollment_course_tees', 'competition_course_tees')",
    )
    assert tablas == []
