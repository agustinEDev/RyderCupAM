"""replace tee category with tee color as tee identifier

La categoría de salida (CHAMPIONSHIP, AMATEUR, SENIOR, FORWARD, JUNIOR) era una
invención propia: ninguna federación la publica. Se comprobó sobre los 802
recorridos federados españoles y sobre campos de Escocia, Inglaterra, Irlanda,
Estados Unidos, Francia y Portugal: todos identifican sus salidas por color o
por un nombre propio, nunca por categoría.

Además la categoría había dejado de identificar unívocamente una salida: desde
que la unicidad pasó a ser por color, un campo puede tener blancas y negras
ambas de campeonato masculino, y elegir "campeonato masculino" era ambiguo.

Lo que identifica una salida pasa a ser (color, género).

La categoría se traduce a color con la convención española, que es la que
seguían los datos existentes.

Revision ID: 91fb1f95660b
Revises: ba02ec557335
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "91fb1f95660b"
down_revision: str | None = "ba02ec557335"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Convención española, que es la que seguían los datos que había.
CATEGORY_TO_COLOR = {
    "CHAMPIONSHIP": "WHITE",
    "AMATEUR": "YELLOW",
    "SENIOR": "BLUE",
    "FORWARD": "RED",
    "JUNIOR": "GREEN",
}
# La vuelta atras necesita una categoria para CADA color admitido, no solo para
# los cinco que existian: un campo con barras negras o doradas dejaria valores
# fuera del enum antiguo y la columna quedaria corrupta. La correspondencia de
# los cinco colores nuevos es aproximada por definicion, porque la categoria que
# se recupera nunca existio para ellos.
COLOR_TO_CATEGORY = {
    "WHITE": "CHAMPIONSHIP",
    "YELLOW": "AMATEUR",
    "BLUE": "SENIOR",
    "RED": "FORWARD",
    "GREEN": "JUNIOR",
    "BLACK": "CHAMPIONSHIP",
    "GOLD": "SENIOR",
    "ORANGE": "JUNIOR",
    "PINK": "FORWARD",
    "OTHER": "AMATEUR",
}

# Las salidas elegidas viven también dentro de JSON: los participantes de una
# partida rápida y los jugadores de cada emparejamiento.
JSONB_COLUMNS = [
    ("quick_matches", "participants"),
    ("matches", "team_a_players"),
    ("matches", "team_b_players"),
]


def _rename_json_key(table: str, column: str, old_key: str, new_key: str) -> str:
    """
    SQL que renombra una clave dentro de un array JSON de objetos.

    Se reconstruye el array elemento a elemento: PostgreSQL no tiene una
    operación de renombrado de clave en su sitio.
    """
    return f"""
        UPDATE {table} SET {column} = (
            SELECT COALESCE(jsonb_agg(
                (elem - '{old_key}') || jsonb_build_object('{new_key}', elem->'{old_key}')
            ), '[]'::jsonb)
            FROM jsonb_array_elements({column}) AS elem
        )
        WHERE {column} IS NOT NULL
          AND jsonb_typeof({column}) = 'array'
          AND EXISTS (
              SELECT 1 FROM jsonb_array_elements({column}) AS e
              WHERE e ? '{old_key}'
          )
    """  # noqa: S608


def _translate_json_values(table: str, column: str, key: str, mapping: dict[str, str]) -> str:
    """SQL que traduce los valores de una clave dentro de un array JSON."""
    cases = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items())
    return f"""
        UPDATE {table} SET {column} = (
            SELECT COALESCE(jsonb_agg(
                CASE
                    WHEN elem->>'{key}' IS NULL THEN elem
                    ELSE elem || jsonb_build_object('{key}',
                        CASE elem->>'{key}' {cases} ELSE elem->>'{key}' END)
                END
            ), '[]'::jsonb)
            FROM jsonb_array_elements({column}) AS elem
        )
        WHERE {column} IS NOT NULL AND jsonb_typeof({column}) = 'array'
    """  # noqa: S608


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Inscripciones: la salida elegida pasa a ser un color
    # ------------------------------------------------------------------
    op.alter_column("enrollments", "tee_category", new_column_name="tee_color")
    for category, color in CATEGORY_TO_COLOR.items():
        op.execute(
            f"UPDATE enrollments SET tee_color = '{color}' WHERE tee_color = '{category}'"  # noqa: S608
        )

    # ------------------------------------------------------------------
    # 2. Partidas rápidas y emparejamientos: la salida vive dentro de JSON
    # ------------------------------------------------------------------
    for table, column in JSONB_COLUMNS:
        op.execute(_translate_json_values(table, column, "tee_category", CATEGORY_TO_COLOR))
        op.execute(_rename_json_key(table, column, "tee_category", "tee_color"))

    # ------------------------------------------------------------------
    # 3. La categoría desaparece de la definición de la salida
    # ------------------------------------------------------------------
    op.drop_column("golf_course_tees", "tee_category")
    sa.Enum(name="tee_category_enum").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Recrear la categoría a partir del color
    tee_category_enum = sa.Enum(
        "CHAMPIONSHIP", "AMATEUR", "SENIOR", "FORWARD", "JUNIOR", name="tee_category_enum"
    )
    tee_category_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "golf_course_tees",
        sa.Column(
            "tee_category",
            tee_category_enum,
            nullable=False,
            server_default="AMATEUR",
            comment="Categoría normalizada WHS",
        ),
    )
    # Recorre los diez colores, no los cinco antiguos: si no, las barras negras,
    # doradas, naranjas o rosas se quedarian con el valor por defecto.
    for color, category in COLOR_TO_CATEGORY.items():
        op.execute(
            f"UPDATE golf_course_tees SET tee_category = '{category}'::tee_category_enum "  # noqa: S608
            f"WHERE color = '{color}'"
        )

    for table, column in JSONB_COLUMNS:
        op.execute(_rename_json_key(table, column, "tee_color", "tee_category"))
        op.execute(_translate_json_values(table, column, "tee_category", COLOR_TO_CATEGORY))

    for color, category in COLOR_TO_CATEGORY.items():
        op.execute(
            f"UPDATE enrollments SET tee_color = '{category}' WHERE tee_color = '{color}'"  # noqa: S608
        )
    op.alter_column("enrollments", "tee_color", new_column_name="tee_category")
