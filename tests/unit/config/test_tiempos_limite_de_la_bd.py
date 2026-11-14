"""
La base de datos no deja conexiones colgadas sin límite (auditoría de la fase 6, DB-04).

En producción no había ningún tiempo límite: una consulta lenta, o una petición que muere
a mitad de una transacción, retenía una conexión del pool (5 + 10 por proceso) y sus
bloqueos indefinidamente, y la API se podía atascar. Y una migración esperaba sin límite
a un bloqueo, con la API en cola detrás.

    caso                                                 | qué pasa
    -----------------------------------------------------|--------------------------------
    T1 cada conexión de la API                           | statement_timeout = 15 s
    T2 cada conexión de la API                           | idle_in_transaction = 30 s
    T1/T2 se pueden ajustar sin desplegar                | DB_STATEMENT_TIMEOUT_MS, DB_IDLE_IN_TRANSACTION_TIMEOUT_MS
    T3 las migraciones                                   | lock_timeout = 5 s antes de migrar
"""

import importlib
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]


def _motor_con(monkeypatch, **entorno) -> dict:
    """Recarga `src.config.database` y devuelve con qué argumentos crea el motor."""
    import sqlalchemy.ext.asyncio as sa_async

    from src.config import database

    for nombre, valor in entorno.items():
        monkeypatch.setenv(nombre, valor)
    llamadas: list[dict] = []

    def crea(url, **kwargs):
        llamadas.append(kwargs)
        return object()

    monkeypatch.setattr(sa_async, "create_async_engine", crea)
    monkeypatch.setattr(sa_async, "async_sessionmaker", lambda **_: None)
    try:
        importlib.reload(database)
    finally:
        monkeypatch.undo()
        importlib.reload(database)
    [kwargs] = llamadas
    return kwargs


def test_t1_t2_every_api_connection_has_statement_and_idle_transaction_timeouts(monkeypatch):
    ajustes = _motor_con(monkeypatch)["connect_args"]["server_settings"]

    assert ajustes == {
        "statement_timeout": "15000",
        "idle_in_transaction_session_timeout": "30000",
    }


def test_the_timeouts_can_be_changed_from_the_environment(monkeypatch):
    ajustes = _motor_con(
        monkeypatch,
        DB_STATEMENT_TIMEOUT_MS="30000",
        DB_IDLE_IN_TRANSACTION_TIMEOUT_MS="60000",
    )["connect_args"]["server_settings"]

    assert ajustes["statement_timeout"] == "30000"
    assert ajustes["idle_in_transaction_session_timeout"] == "60000"


def test_t3_migrations_wait_at_most_five_seconds_for_a_lock():
    """
    Antes de configurar el contexto: así vale para todas las migraciones del arranque,
    también las de `autocommit_block()` (el SET es de la sesión, no de la transacción).
    """
    env = (RAIZ / "alembic" / "env.py").read_text()
    online = env[env.index("def run_migrations_online") :]

    puesto = re.search(r"SET lock_timeout = '5s'", online)
    configura = online.index("context.configure(")
    assert puesto is not None
    assert puesto.start() < configura


@pytest.mark.parametrize("valor", ["0", "-1", "abc"])
def test_a_wrong_value_does_not_remove_the_timeout(monkeypatch, valor):
    """Un 0 en Postgres es «sin límite»: un valor que no sea un número positivo vuelve al
    de por defecto, no quita el límite."""
    ajustes = _motor_con(monkeypatch, DB_STATEMENT_TIMEOUT_MS=valor)["connect_args"][
        "server_settings"
    ]

    assert ajustes["statement_timeout"] == "15000"
