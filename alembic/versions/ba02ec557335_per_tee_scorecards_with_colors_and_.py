"""per tee scorecards with colors and meters

Los hoyos pasan a colgar de la salida y no del campo: el par, el índice de
dificultad y la distancia dependen de la barra desde la que se juega. Esto
ocurre en 77 de los 802 recorridos federados españoles, y en la mayoría la
diferencia es entre colores del mismo género, no entre géneros.

La tarjeta del campo (GolfCourse.holes) pasa a ser derivada: se calcula desde
la primera salida al consultarla, así que golf_course_holes desaparece.

Revision ID: ba02ec557335
Revises: f7c2a9d4e6b8
Create Date: 2026-08-11

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ba02ec557335"
down_revision: str | None = "f7c2a9d4e6b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEE_COLORS = (
    "RED",
    "YELLOW",
    "BLUE",
    "WHITE",
    "GREEN",
    "ORANGE",
    "BLACK",
    "PINK",
    "GOLD",
    "OTHER",
)

# Los campos existentes guardan el color como texto libre en `identifier`.
# Este mapeo recupera esa información en vez de dejarlos todos en OTHER.
IDENTIFIER_TO_COLOR = {
    "RED": ("rojo", "rojas", "red"),
    "YELLOW": ("amarillo", "amarillas", "yellow"),
    "BLUE": ("azul", "azules", "blue"),
    "WHITE": ("blanco", "blancas", "white"),
    "GREEN": ("verde", "verdes", "green"),
    "ORANGE": ("naranja", "naranjas", "orange"),
    "BLACK": ("negro", "negras", "black"),
    "PINK": ("rosa", "rosas", "pink"),
    "GOLD": ("oro", "dorado", "doradas", "gold"),
}


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Color de las barras
    # ------------------------------------------------------------------
    tee_color_enum = sa.Enum(*TEE_COLORS, name="tee_color_enum")
    tee_color_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "golf_course_tees",
        sa.Column(
            "color",
            tee_color_enum,
            nullable=False,
            server_default="OTHER",
            comment="Color de las barras. Independiente de la categoría",
        ),
    )

    # Recupera el color desde el identificador libre, que es donde se venía
    # escribiendo ("Blanco", "Amarillo", ...).
    for color, needles in IDENTIFIER_TO_COLOR.items():
        conditions = " OR ".join(f"LOWER(TRIM(identifier)) = '{n}'" for n in needles)
        op.execute(
            f"UPDATE golf_course_tees SET color = '{color}'::tee_color_enum "
            f"WHERE {conditions}"
        )

    # El identificador pasa a ser opcional: el color ya identifica la salida.
    op.alter_column("golf_course_tees", "identifier", nullable=True)

    # Una salida sin color reconocible necesita identificador para poder
    # distinguirse de otra igual.
    op.execute(
        "UPDATE golf_course_tees SET identifier = 'Salida ' || id::text "
        "WHERE color = 'OTHER' AND (identifier IS NULL OR TRIM(identifier) = '')"
    )
    op.create_check_constraint(
        "ck_tees_other_color_needs_identifier",
        "golf_course_tees",
        "color <> 'OTHER' OR identifier IS NOT NULL",
    )

    # ------------------------------------------------------------------
    # 2. Rangos de rating: los absolutos, unión de todos los tipos de campo.
    #    El rango estricto de cada tipo lo valida el dominio, porque un CHECK
    #    tendría que consultar golf_courses para conocer el tipo.
    # ------------------------------------------------------------------
    op.drop_constraint("ck_tees_course_rating_range", "golf_course_tees", type_="check")
    op.drop_constraint("ck_tees_slope_rating_range", "golf_course_tees", type_="check")
    op.create_check_constraint(
        "ck_tees_course_rating_range",
        "golf_course_tees",
        "course_rating >= 45.0 AND course_rating <= 90.0",
    )
    op.create_check_constraint(
        "ck_tees_slope_rating_range",
        "golf_course_tees",
        "slope_rating >= 40 AND slope_rating <= 160",
    )

    # ------------------------------------------------------------------
    # 3. Unicidad por salida: pasa de (categoría, género) a color o
    #    identificador. Un campo puede tener blancas y negras y ser ambas de
    #    campeonato masculino, así que la categoría ya no distingue.
    # ------------------------------------------------------------------
    #    Se resuelve con dos índices parciales en vez de una expresión CASE:
    #    el cast de un enum a texto no es IMMUTABLE y PostgreSQL no lo admite
    #    dentro de un índice.
    op.execute("DROP INDEX IF EXISTS uq_golf_course_tees_cat_gender")
    op.execute(
        "CREATE UNIQUE INDEX uq_golf_course_tees_color_gender "
        "ON golf_course_tees (golf_course_id, color, COALESCE(tee_gender, 'NONE')) "
        "WHERE color <> 'OTHER'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_golf_course_tees_identifier_gender "
        "ON golf_course_tees (golf_course_id, identifier, COALESCE(tee_gender, 'NONE')) "
        "WHERE color = 'OTHER'"
    )

    # ------------------------------------------------------------------
    # 4. Tarjeta por salida
    # ------------------------------------------------------------------
    op.create_table(
        "golf_course_tee_holes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tee_id", sa.Integer(), nullable=False),
        sa.Column("hole_number", sa.Integer(), nullable=False, comment="Número de hoyo (1-18)"),
        sa.Column("par", sa.Integer(), nullable=False, comment="Par del hoyo (3-6)"),
        sa.Column(
            "stroke_index", sa.Integer(), nullable=False, comment="Índice de dificultad (1-18)"
        ),
        sa.Column(
            "meters", sa.Integer(), nullable=True, comment="Distancia desde esta salida, en metros"
        ),
        sa.ForeignKeyConstraint(["tee_id"], ["golf_course_tees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("hole_number >= 1 AND hole_number <= 18", name="ck_tee_holes_number_range"),
        sa.CheckConstraint("par >= 3 AND par <= 6", name="ck_tee_holes_par_range"),
        sa.CheckConstraint(
            "stroke_index >= 1 AND stroke_index <= 18", name="ck_tee_holes_stroke_index_range"
        ),
        sa.CheckConstraint(
            "meters IS NULL OR (meters >= 20 AND meters <= 700)", name="ck_tee_holes_meters_range"
        ),
        sa.UniqueConstraint("tee_id", "hole_number", name="uq_tee_holes_number"),
        sa.UniqueConstraint("tee_id", "stroke_index", name="uq_tee_holes_stroke_index"),
        comment="Hoyos de cada salida (18 por salida) con par, dificultad y distancia",
    )
    op.create_index("ix_tee_holes_tee_id", "golf_course_tee_holes", ["tee_id"])

    # Replica la tarjeta del campo en cada una de sus salidas. Sin distancias,
    # porque hasta ahora no se guardaban.
    op.execute(
        "INSERT INTO golf_course_tee_holes (tee_id, hole_number, par, stroke_index, meters) "
        "SELECT t.id, h.hole_number, h.par, h.stroke_index, NULL "
        "FROM golf_course_tees t "
        "JOIN golf_course_holes h ON h.golf_course_id = t.golf_course_id"
    )

    # ------------------------------------------------------------------
    # 5. La tarjeta del campo pasa a ser derivada
    # ------------------------------------------------------------------
    op.drop_table("golf_course_holes")


def downgrade() -> None:
    # Recrea la tarjeta a nivel de campo
    op.create_table(
        "golf_course_holes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("golf_course_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("hole_number", sa.Integer(), nullable=False),
        sa.Column("par", sa.Integer(), nullable=False),
        sa.Column("stroke_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["golf_course_id"], ["golf_courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("hole_number >= 1 AND hole_number <= 18", name="ck_holes_number_range"),
        sa.CheckConstraint("par >= 3 AND par <= 5", name="ck_holes_par_range"),
        sa.CheckConstraint(
            "stroke_index >= 1 AND stroke_index <= 18", name="ck_holes_stroke_index_range"
        ),
        sa.UniqueConstraint("golf_course_id", "hole_number", name="uq_golf_course_holes_number"),
        sa.UniqueConstraint(
            "golf_course_id", "stroke_index", name="uq_golf_course_holes_stroke_index"
        ),
    )

    # Reconstruye la tarjeta del campo desde una salida cualquiera, quedándose
    # con el par más frecuente por hoyo. Los pares 6 no caben en el CHECK
    # antiguo y se degradan a 5.
    op.execute(
        "INSERT INTO golf_course_holes (golf_course_id, hole_number, par, stroke_index) "
        "SELECT DISTINCT ON (t.golf_course_id, th.hole_number) "
        "t.golf_course_id, th.hole_number, LEAST(th.par, 5), th.stroke_index "
        "FROM golf_course_tee_holes th "
        "JOIN golf_course_tees t ON t.id = th.tee_id "
        "ORDER BY t.golf_course_id, th.hole_number, th.id"
    )

    op.drop_index("ix_tee_holes_tee_id", table_name="golf_course_tee_holes")
    op.drop_table("golf_course_tee_holes")

    op.execute("DROP INDEX IF EXISTS uq_golf_course_tees_color_gender")
    op.execute("DROP INDEX IF EXISTS uq_golf_course_tees_identifier_gender")
    op.execute(
        "CREATE UNIQUE INDEX uq_golf_course_tees_cat_gender "
        "ON golf_course_tees (golf_course_id, tee_category, COALESCE(tee_gender, 'NONE'))"
    )

    op.drop_constraint("ck_tees_course_rating_range", "golf_course_tees", type_="check")
    op.drop_constraint("ck_tees_slope_rating_range", "golf_course_tees", type_="check")
    op.create_check_constraint(
        "ck_tees_course_rating_range",
        "golf_course_tees",
        "course_rating >= 50.0 AND course_rating <= 90.0",
    )
    op.create_check_constraint(
        "ck_tees_slope_rating_range",
        "golf_course_tees",
        "slope_rating >= 55 AND slope_rating <= 155",
    )

    op.drop_constraint("ck_tees_other_color_needs_identifier", "golf_course_tees", type_="check")
    op.execute("UPDATE golf_course_tees SET identifier = 'Salida' WHERE identifier IS NULL")
    op.alter_column("golf_course_tees", "identifier", nullable=False)
    op.drop_column("golf_course_tees", "color")
    sa.Enum(name="tee_color_enum").drop(op.get_bind(), checkfirst=True)
