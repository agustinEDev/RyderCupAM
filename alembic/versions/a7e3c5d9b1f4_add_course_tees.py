"""Add enrollment_course_tees and competition_course_tees: tees per course (20 nov 2026)

Decidido con Agustín (barras por campo): cada inscripción tiene su barra general
(`enrollments.tee_color`), y en cada campo de la competición la pisan, por este
orden, el cambio propio de esa inscripción para ese campo (R1) y la barra que el
organizador fija en el campo para todos los de un género (R2). Sin ninguno
cuenta la general (R3), y si el campo no la tiene no se elige otra sola (R4).

- `enrollment_course_tees`: (inscripción, campo) → barra. Clave primaria.
- `competition_course_tees`: (competición, campo, género) → barra. Clave primaria.

Las dos se van con su inscripción o su competición, y con el campo (ON DELETE
CASCADE). Quitar un campo de una competición (que no borra el campo) borra sus
filas desde el caso de uso.

Nacen vacías: hasta hoy no había cambios por campo, así que nadie cambia de barra
al subir. Solo SQL plano: cabe en el guion del modo offline. La versión anterior
no las conoce: convive con ellas sin tocarlas.

Revision ID: a7e3c5d9b1f4
Revises: b29a88392439
Create Date: 2026-11-20

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a7e3c5d9b1f4"
down_revision = "b29a88392439"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea las dos tablas, vacías."""
    # Las claves ajenas tocan `enrollments`, `competitions` y `golf_courses`: mejor
    # fallar a los 5 s que dejar la app esperando. SET LOCAL: solo en esta transacción.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "enrollment_course_tees",
        sa.Column(
            "enrollment_id",
            sa.CHAR(length=36),
            sa.ForeignKey("enrollments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "golf_course_id",
            UUID(as_uuid=True),
            sa.ForeignKey("golf_courses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tee_color",
            sa.String(20),
            nullable=False,
            comment="La barra que juega esa inscripción en ese campo (R1)",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "competition_course_tees",
        sa.Column(
            "competition_id",
            sa.CHAR(length=36),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "golf_course_id",
            UUID(as_uuid=True),
            sa.ForeignKey("golf_courses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("gender", sa.String(10), primary_key=True, comment="MALE o FEMALE"),
        sa.Column(
            "tee_color",
            sa.String(20),
            nullable=False,
            comment="La barra de ese campo para todos los de ese género (R2)",
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Quita las dos tablas: la versión anterior no las conoce."""
    op.drop_table("competition_course_tees")
    op.drop_table("enrollment_course_tees")
