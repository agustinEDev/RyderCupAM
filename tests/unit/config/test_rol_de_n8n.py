"""
El script que deja a n8n leyendo solo las columnas del informe (DB-01, auditoría del 16
nov 2026), scripts/db/rol_de_n8n.sql.

No se ejecuta en los tests (lo ejecuta Agustín a mano en Render). Aquí se vigila lo que lo
haría fallar allí: una columna concedida que no existe (el GRANT aborta la transacción),
una concedida que no está en la comprobación final (la comprobación aborta), o un cambio
que vuelva a dar una tabla entera.
"""

import re
from pathlib import Path

from src.config.mappers import start_all_mappers
from src.shared.infrastructure.persistence.sqlalchemy.base import metadata

RAIZ = Path(__file__).resolve().parents[3]
SCRIPT = (RAIZ / "scripts" / "db" / "rol_de_n8n.sql").read_text(encoding="utf-8")
GRANT = re.compile(r"^GRANT SELECT \(([^)]*)\) ON public\.(\w+) TO n8n_lectura;$", re.MULTILINE)

# Lo que lee la consulta del informe de los lunes (~/n8n-cbg/workflows/informe-semanal.json)
DEL_INFORME = {
    "users.is_active",
    "users.created_at",
    "users.first_name",
    "users.last_name",
    "competitions.created_at",
    "competitions.name",
    "competitions.status",
    "enrollments.created_at",
    "quick_matches.created_at",
    "quick_matches.status",
    "quick_matches.updated_at",
}


def _concedidas() -> set[str]:
    return {
        f"{tabla}.{columna.strip()}"
        for columnas, tabla in GRANT.findall(SCRIPT)
        for columna in columnas.split(",")
    }


def _comprobadas() -> set[str]:
    bloque = re.search(r"esperadas text\[\] := ARRAY\[(.*?)\];", SCRIPT, re.DOTALL)
    assert bloque, "No se encuentra la lista de la comprobación del paso 5"
    return set(re.findall(r"'([\w.]+)'", bloque.group(1)))


def test_it_grants_exactly_the_columns_of_the_weekly_report():
    """
    Given: el script
    When: se leen sus GRANT de columnas
    Then: son exactamente las columnas que lee el informe, ni una más
    """
    assert _concedidas() == DEL_INFORME


def test_the_final_check_expects_the_same_columns_it_grants():
    """
    Given: el script
    When: se compara la comprobación del paso 5 con los GRANT
    Then: esperan lo mismo (si no, el script se pararía siempre en Render)
    """
    assert _comprobadas() == _concedidas()


def test_every_granted_column_exists_in_the_schema():
    """
    Given: las tablas de la app
    When: se busca cada columna concedida
    Then: existe (un GRANT a una columna que no existe aborta el script)
    """
    start_all_mappers()
    tablas = metadata.tables

    faltan = {
        nombre
        for nombre in _concedidas()
        | {"users.password", "users.email", "users.password_reset_token"}
        if nombre.split(".")[0] not in tablas
        or nombre.split(".")[1] not in tablas[nombre.split(".")[0]].c
    }

    assert faltan == set()


def test_no_whole_table_is_granted():
    """
    Given: el script
    When: se buscan GRANT sin lista de columnas
    Then: no hay ninguno
    """
    assert not re.search(r"^GRANT SELECT ON", SCRIPT, re.MULTILINE)
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM n8n_lectura;" in SCRIPT
