"""
Con qué usuario entran las migraciones (auditoría de la fase 6, DB-01).

La API puede entrar con un usuario que solo maneja filas (`DATABASE_URL`) y las
migraciones con el dueño de la base (`MIGRATIONS_DATABASE_URL`), que es quien puede
cambiar la estructura. Sin la segunda, las migraciones usan la primera, como hasta ahora.
El usuario de la API lo crea `scripts/db/rol_de_la_api.sql`.
"""

import os
from collections.abc import Mapping

VARIABLE_DE_LAS_MIGRACIONES = "MIGRATIONS_DATABASE_URL"


def url_de_las_migraciones(entorno: Mapping[str, str] = os.environ) -> str | None:
    """`MIGRATIONS_DATABASE_URL` si tiene valor; si no, `DATABASE_URL`; si no, None."""
    for nombre in (VARIABLE_DE_LAS_MIGRACIONES, "DATABASE_URL"):
        valor = (entorno.get(nombre) or "").strip()
        if valor:
            return valor
    return None
