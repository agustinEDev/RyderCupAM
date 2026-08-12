"""add provenance to golf courses

Los campos de golf pasan a guardar de dónde salen sus datos: origen, id en la
fuente externa y fecha de importación, más los hoyos que tiene el campo sobre
el terreno.

El origen es un enum y no texto libre para que no acaben conviviendo 'RFEG',
'rfeg' y 'R.F.E.G.' señalando lo mismo. Empieza con MANUAL y RFEG; cada
federación nueva será un valor más.

El identificador externo es nullable a propósito: no todas las federaciones
publican un id estable por recorrido, y el modelo tiene que admitir importar de
países cuya fuente no lo tenga.

Sin estas columnas, reconocer un campo ya importado dependería de comparar
nombres, que se rompe en cuanto un admin renombra un campo: la siguiente
importación lo duplicaría.

`physical_holes` distingue los recorridos que sobre el terreno son de nueve
hoyos jugados dos veces. La tarjeta federada siempre es de 18, así que sin esta
marca no hay forma de saberlo. NULL significa que no consta, que es el caso de
todos los campos anteriores: a nadie se le preguntó al darlos de alta.

Revision ID: e7f2b3c9d418
Revises: c4d8e1a72b93
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f2b3c9d418"
down_revision: str | None = "c4d8e1a72b93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COURSE_SOURCE_VALUES = ("MANUAL", "RFEG")


def upgrade() -> None:
    course_source_enum = sa.Enum(*COURSE_SOURCE_VALUES, name="course_source_enum")
    course_source_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "golf_courses",
        sa.Column(
            "source",
            course_source_enum,
            nullable=False,
            server_default="MANUAL",
            comment="Origen de los datos (MANUAL, RFEG, ...)",
        ),
    )
    op.add_column(
        "golf_courses",
        sa.Column(
            "external_id",
            sa.String(100),
            nullable=True,
            comment="Identificador del campo en la fuente externa, si la fuente publica uno",
        ),
    )
    op.add_column(
        "golf_courses",
        sa.Column(
            "imported_at",
            sa.DateTime(),
            nullable=True,
            comment="Cuándo se importó desde la fuente externa",
        ),
    )
    op.add_column(
        "golf_courses",
        sa.Column(
            "physical_holes",
            sa.Integer(),
            nullable=True,
            comment="Hoyos sobre el terreno (9 o 18). NULL si no consta",
        ),
    )

    op.create_check_constraint(
        "ck_golf_courses_physical_holes_values",
        "golf_courses",
        "physical_holes IS NULL OR physical_holes IN (9, 18)",
    )
    op.create_check_constraint(
        "ck_golf_courses_provenance_consistency",
        "golf_courses",
        "(source = 'MANUAL' AND external_id IS NULL AND imported_at IS NULL) "
        "OR (source <> 'MANUAL' AND imported_at IS NOT NULL)",
    )

    # Reconocer un campo ya importado tiene que ser una búsqueda directa: el
    # importador la hace una vez por recorrido, 802 veces seguidas. Es único
    # porque dos campos no pueden ser el mismo recorrido de la misma fuente, y
    # parcial porque los campos manuales no tienen id externo y todos ellos
    # chocarían entre sí en un índice normal.
    op.create_index(
        "uq_golf_courses_source_external_id",
        "golf_courses",
        ["source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_golf_courses_source_external_id", table_name="golf_courses")
    op.drop_constraint("ck_golf_courses_provenance_consistency", "golf_courses", type_="check")
    op.drop_constraint("ck_golf_courses_physical_holes_values", "golf_courses", type_="check")
    op.drop_column("golf_courses", "physical_holes")
    op.drop_column("golf_courses", "imported_at")
    op.drop_column("golf_courses", "external_id")
    op.drop_column("golf_courses", "source")

    sa.Enum(name="course_source_enum").drop(op.get_bind(), checkfirst=True)
