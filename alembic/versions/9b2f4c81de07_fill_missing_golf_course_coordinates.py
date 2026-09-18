"""fill missing golf course coordinates

Trece de los 805 campos no traen coordenadas de la importación de la RFEG, y sin
ellas no se puede deducir su zona horaria: su anotación no se abre sola y hay que
pulsar START (BE #305).

Las coordenadas se buscaron una a una el 18 sep 2026 y se comprobó que cada una
cae en su municipio:

- OpenStreetMap, nodo etiquetado como campo de golf: Estepona Golf, Compostela
  (los dos recorridos comparten club), Praia D'El Rey, Royal Óbidos, Grandvalira
  (Golf Soldeu, Canillo), La Finca Golf (Pozuelo) y Mas Torrellas.
- Código Plus de Google Maps, con precisión de unos 14 m: La Loma (Córdoba),
  Bocigas (este último apareció además en OpenStreetMap, sin nombre, a 236 m),
  San Roque New (a 200 m de las coordenadas que publica el club, que valen para
  todo el complejo y no para este recorrido), La Resina (a 270 m del vial de la
  urbanización) e Isla del Fraile (a 650 m del vial del complejo). En los dos
  últimos el vial era lo único que había, y ahora apuntan al campo.

Se identifica cada campo por su `external_id` de la RFEG, que es estable, y por
el nombre solo los dos portugueses, dados de alta a mano y sin identificador.

Solo rellena lo que está vacío: si alguien ya puso coordenadas, se respetan. Y
después recalcula el huso de todo campo que tenga coordenadas y no lo tenga, con
la misma regla de la migración anterior.

Revision ID: 9b2f4c81de07
Revises: 7c3e91a45d18
Create Date: 2026-09-18

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "9b2f4c81de07"
down_revision = "7c3e91a45d18"
branch_labels = None
depends_on = None


COORDENADAS: list[tuple[str | None, str, float, float]] = [
    # identificador de la RFEG (o None), nombre, latitud, longitud
    ("591:BOCIGAS", "Bocigas", 41.22994, -4.67931),
    ("1119:COMPOSTELA P P CORTO", "Compostela P&P Corto", 42.92283, -8.48453),
    ("1119:COMPOSTELA P P LARGO", "Compostela P&P Largo", 42.92283, -8.48453),
    ("1117:ESTEPONA GOLF", "Estepona Golf", 36.41297, -5.21219),
    ("1110:GRANDVALIRA", "Grandvalira", 42.56253, 1.66425),
    ("1122:ISLA DEL FRAILE P P", "Isla del Fraile - P&P", 37.41844, -1.55494),
    ("1126:LAFINCA GOLF", "La Finca Golf - Lafinca Golf", 40.40260, -3.79803),
    ("1137:LA LOMA", "La Loma", 37.89131, -4.82531),
    ("1108:LA RESINA", "La Resina", 36.46494, -5.07519),
    ("1116:MAS TORRELLAS", "Mas Torrellas", 41.81480, 3.01834),
    ("1133:SAN ROQUE NEW", "San Roque New", 36.26606, -5.33606),
    (None, "Praia D'El Rey Golf & Beach Resort", 39.38933, -9.28237),
    (None, "Royal Óbidos Spa & Golf Resort", 39.40788, -9.24873),
]


def upgrade() -> None:
    if op.get_context().as_sql:
        # Modo offline (`alembic upgrade --sql`, que el CI usa para validar): la
        # conexión solo escribe el guion y su `execute` devuelve None, así que la
        # consulta de los puntos no se puede hacer. Esta migración es solo datos,
        # de modo que el guion no lleva nada suyo; las coordenadas y los husos los
        # pone cuando corre contra la base de datos
        return

    conexion = op.get_bind()

    for external_id, nombre, latitude, longitude in COORDENADAS:
        if external_id:
            criterio = "external_id = :external_id"
            parametros = {"external_id": external_id}
        else:
            criterio = "name = :nombre"
            parametros = {"nombre": nombre}

        conexion.execute(
            sa.text(
                "UPDATE golf_courses SET latitude = :lat, longitude = :lon "
                f"WHERE {criterio} AND latitude IS NULL AND longitude IS NULL"
            ),
            {**parametros, "lat": latitude, "lon": longitude},
        )

    # Y su zona horaria, ahora que ya se puede deducir. Mismo criterio que la
    # migración anterior: se agrupa por punto, porque dos recorridos del mismo
    # club comparten coordenadas
    from tzfpy import get_tz  # noqa: PLC0415

    puntos = conexion.execute(
        sa.text(
            "SELECT DISTINCT latitude, longitude FROM golf_courses "
            "WHERE timezone IS NULL AND latitude IS NOT NULL AND longitude IS NOT NULL"
        )
    ).fetchall()

    for latitude, longitude in puntos:
        try:
            zona = get_tz(longitude, latitude)
        except Exception:
            zona = None
        if not zona:
            continue
        conexion.execute(
            sa.text(
                "UPDATE golf_courses SET timezone = :zona "
                "WHERE latitude = :lat AND longitude = :lon AND timezone IS NULL"
            ),
            {"zona": zona, "lat": latitude, "lon": longitude},
        )


def downgrade() -> None:
    """
    Deja los trece campos como estaban: sin coordenadas y sin zona.

    Se identifica cada uno igual que en el upgrade, y solo se vacía lo que esta
    migración puso, comparando el valor.
    """
    conexion = op.get_bind()

    for external_id, nombre, latitude, longitude in COORDENADAS:
        if external_id:
            criterio = "external_id = :external_id"
            parametros = {"external_id": external_id}
        else:
            criterio = "name = :nombre"
            parametros = {"nombre": nombre}

        conexion.execute(
            sa.text(
                "UPDATE golf_courses SET latitude = NULL, longitude = NULL, timezone = NULL "
                f"WHERE {criterio} AND latitude = :lat AND longitude = :lon"
            ),
            {**parametros, "lat": latitude, "lon": longitude},
        )
