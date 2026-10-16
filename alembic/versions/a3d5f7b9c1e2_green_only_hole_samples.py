"""Green-only hole samples (BE #575, 17 oct 2026)

Decidido con Agustín el 17 oct 2026: quien abre el mapa a mitad de hoyo no está
en la salida y marca solo el green. Su muestra va sin salida ni codos, y el
siguiente que esté en la salida completa el hoyo con ella. La salida pasa a
admitir NULL, y una restricción impide medias salidas o codos sin salida. Las
muestras guardadas no cambian. Solo SQL plano: cabe en el guion del modo offline.

Revision ID: a3d5f7b9c1e2
Revises: 5206fa18886b
Create Date: 2026-10-17

"""

from alembic import op

revision = "a3d5f7b9c1e2"
down_revision = "5206fa18886b"
branch_labels = None
depends_on = None

_CHECK = "ck_golf_course_hole_samples_green_only"


def upgrade() -> None:
    """La salida, opcional; sin ella, ni codos."""
    op.alter_column("golf_course_hole_samples", "tee_latitude", nullable=True)
    op.alter_column("golf_course_hole_samples", "tee_longitude", nullable=True)
    op.create_check_constraint(
        _CHECK,
        "golf_course_hole_samples",
        "(tee_latitude IS NULL AND tee_longitude IS NULL AND jsonb_array_length(bends) = 0)"
        " OR (tee_latitude IS NOT NULL AND tee_longitude IS NOT NULL)",
    )
    # Desde hoy son tres por hoyo, de cualquier barra
    op.create_table_comment(
        "golf_course_hole_samples",
        "Muestras anónimas de los hoyos (las tres primeras por hoyo), sin autor ni hora",
    )
    op.alter_column(
        "golf_course_hole_samples", "tee_latitude", comment="Salida (NULL: solo green)"
    )


def downgrade() -> None:
    """Las de solo green no caben en el esquema de antes: se borran."""
    op.drop_constraint(_CHECK, "golf_course_hole_samples", type_="check")
    op.execute("DELETE FROM golf_course_hole_samples WHERE tee_latitude IS NULL")
    op.alter_column("golf_course_hole_samples", "tee_latitude", nullable=False, comment="Salida")
    op.alter_column("golf_course_hole_samples", "tee_longitude", nullable=False)
    op.create_table_comment(
        "golf_course_hole_samples",
        "Muestras anónimas de los hoyos (las tres primeras por barra), sin autor ni hora",
    )
