"""add location to golf courses

Los campos de golf pasan a guardar dónde están: coordenadas, dirección postal,
localidad y provincia. Es la base para proponer campos cercanos a la ubicación
del dispositivo en las partidas rápidas.

Todo es opcional. Los campos que ya existen se quedan sin ubicación, y las
federaciones tampoco la publican siempre (11 de los 442 clubes federados
españoles no traen coordenadas).

Las coordenadas van juntas o no van: media coordenada no sitúa nada en un mapa
y una búsqueda por cercanía que la aceptara devolvería resultados arbitrarios.
Lo garantiza un CHECK, no solo el dominio, porque la importación masiva escribe
muchas filas de golpe y un dato a medias pasaría inadvertido.

Revision ID: c4d8e1a72b93
Revises: 91fb1f95660b
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d8e1a72b93"
down_revision: str | None = "91fb1f95660b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "golf_courses",
        sa.Column("latitude", sa.Float(), nullable=True, comment="Latitud en grados decimales"),
    )
    op.add_column(
        "golf_courses",
        sa.Column("longitude", sa.Float(), nullable=True, comment="Longitud en grados decimales"),
    )
    op.add_column(
        "golf_courses",
        sa.Column("address", sa.String(300), nullable=True, comment="Dirección postal completa"),
    )
    op.add_column(
        "golf_courses",
        sa.Column("city", sa.String(100), nullable=True, comment="Localidad"),
    )
    op.add_column(
        "golf_courses",
        sa.Column("province", sa.String(100), nullable=True, comment="Provincia o región"),
    )

    op.create_check_constraint(
        "ck_golf_courses_latitude_range",
        "golf_courses",
        "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
    )
    op.create_check_constraint(
        "ck_golf_courses_longitude_range",
        "golf_courses",
        "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
    )
    op.create_check_constraint(
        "ck_golf_courses_coordinates_together",
        "golf_courses",
        "(latitude IS NULL) = (longitude IS NULL)",
    )

    # Índice para la búsqueda por cercanía. Es un filtro por caja (un rango de
    # latitud y otro de longitud) antes de calcular distancias reales, que es
    # como se resuelve "campos cerca de mí" sin PostGIS. Parcial, porque las
    # filas sin coordenadas nunca entran en esa consulta.
    op.create_index(
        "ix_golf_courses_coordinates",
        "golf_courses",
        ["latitude", "longitude"],
        postgresql_where=sa.text("latitude IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_golf_courses_coordinates", table_name="golf_courses")
    op.drop_constraint("ck_golf_courses_coordinates_together", "golf_courses", type_="check")
    op.drop_constraint("ck_golf_courses_longitude_range", "golf_courses", type_="check")
    op.drop_constraint("ck_golf_courses_latitude_range", "golf_courses", type_="check")
    op.drop_column("golf_courses", "province")
    op.drop_column("golf_courses", "city")
    op.drop_column("golf_courses", "address")
    op.drop_column("golf_courses", "longitude")
    op.drop_column("golf_courses", "latitude")
