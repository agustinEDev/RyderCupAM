"""
La base de datos no deja conexiones colgadas sin límite (auditoría de la fase 6, DB-04).

En producción no había ningún tiempo límite: una consulta lenta, o una petición que muere
a mitad de una transacción, retenía una conexión del pool (5 + 10 por proceso) y sus
bloqueos indefinidamente, y la API se podía atascar. Y una migración esperaba sin límite
a un bloqueo, con la API en cola detrás.

    caso                                                 | qué pasa
    -----------------------------------------------------|--------------------------------
    T1 cada conexión de la API                           | statement_timeout = 15 s
    T2 cada conexión de la API                           | idle_in_transaction = 2 min
    T1/T2 se pueden ajustar sin desplegar                | DB_STATEMENT_TIMEOUT_MS,
                                                         | DB_IDLE_IN_TRANSACTION_TIMEOUT_MS
    un valor que no sirve                                | el de por defecto, nunca «sin límite»
    el motor de la API                                   | usa esos ajustes
    T3 las migraciones                                   | lock_timeout = 5 s antes de migrar
"""

import re
from pathlib import Path

import pytest

from src.config.database import ajustes_de_la_conexion

RAIZ = Path(__file__).resolve().parents[3]


def test_t1_t2_every_api_connection_has_statement_and_idle_transaction_timeouts(monkeypatch):
    monkeypatch.delenv("DB_STATEMENT_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("DB_IDLE_IN_TRANSACTION_TIMEOUT_MS", raising=False)

    assert ajustes_de_la_conexion() == {
        "server_settings": {
            "statement_timeout": "15000",
            "idle_in_transaction_session_timeout": "120000",
        }
    }


def test_the_timeouts_can_be_changed_from_the_environment(monkeypatch):
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "30000")
    monkeypatch.setenv("DB_IDLE_IN_TRANSACTION_TIMEOUT_MS", "60000")

    ajustes = ajustes_de_la_conexion()["server_settings"]

    assert ajustes["statement_timeout"] == "30000"
    assert ajustes["idle_in_transaction_session_timeout"] == "60000"


@pytest.mark.parametrize("valor", ["0", "-1", "abc"])
def test_a_wrong_value_does_not_remove_the_timeout(monkeypatch, valor):
    """Un 0 en Postgres es «sin límite»: un valor que no sea un número positivo vuelve al
    de por defecto, no quita el límite."""
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", valor)

    assert ajustes_de_la_conexion()["server_settings"]["statement_timeout"] == "15000"


def test_the_api_engine_is_created_with_those_settings():
    fuente = (RAIZ / "src" / "config" / "database.py").read_text()

    llamada = fuente[fuente.index("async_engine = create_async_engine(") :]
    llamada = llamada[: llamada.index("\n)\n")]

    assert "connect_args=AJUSTES_DE_LA_CONEXION" in llamada


def test_t3_migrations_wait_at_most_five_seconds_for_a_lock():
    """
    Antes de configurar el contexto: así vale para todas las migraciones del arranque,
    también las de `autocommit_block()` (el SET es de la sesión, no de la transacción).
    """
    env = (RAIZ / "alembic" / "env.py").read_text()
    online = env[env.index("def run_migrations_online") :]

    puesto = re.search(r"SET lock_timeout = '5s'", online)
    assert puesto is not None
    assert puesto.start() < online.index("context.configure(")
