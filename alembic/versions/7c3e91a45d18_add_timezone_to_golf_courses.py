"""add timezone to golf courses

La anotación de un partido se abre sola a una hora fija por sesión —mañana
06:00, tarde 12:00, noche 18:00— para que una vuelta no se pierda porque nadie
pulsó START con cobertura (BE #305). Esa hora es la LOCAL del campo donde se
juega, así que el huso vive aquí y no en la competición: una competición puede
jugarse en campos de husos distintos, y cada ronda usa el del suyo.

No se puede deducir del país —España tiene dos husos, y también EEUU, Chile o
Australia—, pero sí de las coordenadas, que 792 de los 805 campos ya traen de la
RFEG. Esta migración las traduce con `tzfpy`.

NULL a propósito para los que no tienen coordenadas: **no se adivina**. Un campo
sin huso no abre la anotación sola —sigue necesitando START— y la pantalla de la
competición lo avisa, para que nadie se entere en el campo y sin cobertura.

Revision ID: 7c3e91a45d18
Revises: 43bc18ca6df1
Create Date: 2026-09-18

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "7c3e91a45d18"
down_revision = "43bc18ca6df1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "golf_courses",
        sa.Column("timezone", sa.String(length=64), nullable=True),
    )

    # Relleno desde las coordenadas. Se agrupan por punto: los campos de un mismo
    # club comparten coordenadas (Aldeamayor tiene tres), así que son bastantes
    # menos consultas que filas
    from tzfpy import get_tz  # noqa: PLC0415

    conexion = op.get_bind()
    puntos = conexion.execute(
        sa.text(
            "SELECT DISTINCT latitude, longitude FROM golf_courses "
            "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
        )
    ).fetchall()

    for latitude, longitude in puntos:
        try:
            zona = get_tz(longitude, latitude)
        except Exception:  # noqa: BLE001
            zona = None
        if not zona:
            continue
        conexion.execute(
            sa.text(
                "UPDATE golf_courses SET timezone = :zona "
                "WHERE latitude = :lat AND longitude = :lon"
            ),
            {"zona": zona, "lat": latitude, "lon": longitude},
        )


def downgrade() -> None:
    op.drop_column("golf_courses", "timezone")
