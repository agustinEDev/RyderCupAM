"""
Las migraciones pueden entrar con otro usuario que la API (auditoría de la fase 6, DB-01).

La API corría como dueña de la base: con un fallo que dejara ejecutar SQL, se podían borrar
las tablas o crear un usuario oculto. Ahora la API puede entrar con un usuario que solo
maneja filas (`DATABASE_URL`) y las migraciones con el dueño (`MIGRATIONS_DATABASE_URL`).

    caso                                              | las migraciones usan
    --------------------------------------------------|------------------------------
    R1 con MIGRATIONS_DATABASE_URL                    | MIGRATIONS_DATABASE_URL
    R2 sin ella (o vacía)                             | DATABASE_URL, como hasta hoy
    R1/R3 alembic/env.py, online y offline            | esa misma función
"""

from pathlib import Path

import pytest

from src.config.migraciones import url_de_las_migraciones

RAIZ = Path(__file__).resolve().parents[3]
API = "postgresql://rydercup_app:x@db:5432/rydercup"
DUENO = "postgresql://dueno:y@db:5432/rydercup"


def test_r1_migrations_use_their_own_url_when_there_is_one():
    entorno = {"DATABASE_URL": API, "MIGRATIONS_DATABASE_URL": DUENO}

    assert url_de_las_migraciones(entorno) == DUENO


@pytest.mark.parametrize("propia", [None, "", "   "])
def test_r2_without_it_migrations_use_the_api_url_as_today(propia):
    entorno = {"DATABASE_URL": API}
    if propia is not None:
        entorno["MIGRATIONS_DATABASE_URL"] = propia

    assert url_de_las_migraciones(entorno) == API


def test_r2_without_any_url_there_is_none():
    assert url_de_las_migraciones({}) is None


def test_r1_r3_alembic_takes_the_url_from_that_function_online_and_offline():
    env = (RAIZ / "alembic" / "env.py").read_text()
    offline = env[env.index("def run_migrations_offline") : env.index("def run_migrations_online")]
    online = env[env.index("def run_migrations_online") :]

    assert 'os.getenv("DATABASE_URL")' not in env
    assert "url_de_las_migraciones()" in offline
    assert "url_de_las_migraciones()" in online
